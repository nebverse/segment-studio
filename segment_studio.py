"""Segment Studio — single-class visible-flame mask editing (RGB first).

Tkinter+Pillow+OpenCV UI. SAM2.1 is optional and local; SAM3 via optional
separate environment subprocess. No image/mask mutation unless Save is pressed.
"""
from __future__ import annotations

import json
import math
import os
import queue
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageTk

from mask_utils import (is_rgb_image, binary_mask, mask_pack, mask_unpack, merge_masks,
                        colour_candidate, detect_component_polygon, replace_polygon_component,
                        save_png_atomic, write_manifest, load_image_pairs)
from sam_backends import Sam2Local, SAM2_CONFIGS, sam3_predict

ROOT = Path(__file__).resolve().parent
MAX_UNDO = 10


class FireAnnotator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Segment Studio | Visible-flame annotation')
        self.geometry('1320x880')
        self.minsize(920, 680)
        self.folder = None
        self.ir_folder = None
        self.pairs = {}
        self.images = []
        self.idx = -1
        self.image = None
        self.ir_image = None
        self.image_path = None
        self.mask = None
        self.original_mask = None
        self.pending_candidate = None
        self.pending_model = None
        self.points = []
        self.undo_stack = []
        self.dirty = False
        self.busy = False
        self.mask_status = 'unreviewed'
        self.source = 'manual'
        self.mode = tk.StringVar(value='Paint fire')
        self.brush = tk.DoubleVar(value=14)
        self.model = tk.StringVar(value='SAM2.1 small')
        self.merge = tk.StringVar(value='Add (union)')
        self.prompt_text = tk.StringVar(value='flames')
        self.threshold = tk.DoubleVar(value=0.4)
        self.annotator = tk.StringVar(value=os.environ.get('USERNAME', 'annotator'))
        self.overlay_colour = tk.StringVar(value='Purple')
        self.opacity = tk.DoubleVar(value=0.3)
        self.show_edge = tk.BooleanVar(value=True)
        self.show_candidate = tk.BooleanVar(value=True)
        self.ir_preview = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='Open a folder of RGB fire images to begin.')
        self.image_label = tk.StringVar(value='No image')
        self.counter = tk.StringVar(value='0/0')
        self.scaling = 1.0
        self.offset = (0.0, 0.0)
        self.drag_last = None
        self.pan_last = None
        self.vertex_drag = None
        self.selected_vertex = None
        self.free_poly = []
        self.orig_contour = None
        self.orig_contour_full = None
        self.edit_contour = None
        self.base_before_edit = None
        self.render_task = None
        self.cache_key = None
        self.cache_rgb = None
        self.photo = None
        self.running_queue = queue.Queue()
        self.sam2 = Sam2Local()
        self._build_ui()
        self.after(120, self._check_queue)

    def _build_ui(self):
        row1 = ttk.Frame(self, padding=(8, 7))
        row1.pack(fill='x')
        ttk.Button(row1, text='Open RGB folder', command=self.open_folder).pack(side='left', padx=2)
        ttk.Button(row1, text='IR folder (optional)', command=self.choose_ir_folder).pack(side='left', padx=2)
        ttk.Checkbutton(row1, text='View IR only', variable=self.ir_preview, command=self.toggle_ir).pack(side='left', padx=8)
        ttk.Button(row1, text='◀ Previous', command=lambda: self.navigate(-1)).pack(side='left', padx=4)
        ttk.Button(row1, text='Next ▶', command=lambda: self.navigate(1)).pack(side='left', padx=2)
        ttk.Label(row1, textvariable=self.counter, width=7).pack(side='left', padx=5)
        ttk.Label(row1, textvariable=self.image_label).pack(side='left', padx=6)

        row2 = ttk.Frame(self, padding=(8, 5))
        row2.pack(fill='x')
        ttk.Label(row2, text='Tool:').pack(side='left')
        ttk.Combobox(row2, textvariable=self.mode, width=18, state='readonly',
                     values=['Paint fire', 'Erase', 'SAM positive', 'SAM negative',
                             'Polygon add', 'Polygon erase', 'Edit boundary', 'Pan']).pack(side='left', padx=4)
        ttk.Label(row2, text='Brush px').pack(side='left', padx=(8, 1))
        ttk.Scale(row2, from_=2, to=120, variable=self.brush, length=105).pack(side='left')
        ttk.Button(row2, text='Undo', command=self.undo).pack(side='left', padx=4)
        ttk.Button(row2, text='Finish polygon', command=self.finish_polygon).pack(side='left', padx=3)
        ttk.Button(row2, text='Commit boundary', command=self.commit_boundary).pack(side='left', padx=3)
        ttk.Button(row2, text='Cancel edit', command=self.cancel_edit).pack(side='left', padx=3)
        ttk.Button(row2, text='Clear prompts', command=self.clear_prompts).pack(side='left', padx=3)
        ttk.Button(row2, text='Fit', command=self.fit).pack(side='left', padx=3)
        ttk.Button(row2, text='Clear mask', command=self.clear_mask).pack(side='left', padx=3)

        row3 = ttk.Frame(self, padding=(8, 5))
        row3.pack(fill='x')
        ttk.Label(row3, text='Model:').pack(side='left')
        ttk.Combobox(row3, textvariable=self.model, width=17, state='readonly',
                     values=[*SAM2_CONFIGS, 'SAM3 text', 'Colour demo (not AI)']).pack(side='left', padx=4)
        ttk.Button(row3, text='Run candidate', command=self.run_candidate).pack(side='left', padx=3)
        ttk.Label(row3, text='Apply as:').pack(side='left', padx=(8, 1))
        ttk.Combobox(row3, textvariable=self.merge, width=13, state='readonly',
                     values=['Replace', 'Add (union)', 'Subtract', 'Intersect']).pack(side='left', padx=3)
        ttk.Button(row3, text='Apply candidate', command=self.apply_candidate).pack(side='left', padx=3)
        ttk.Button(row3, text='Discard candidate', command=self.discard_candidate).pack(side='left', padx=3)
        ttk.Label(row3, text='SAM3 text:').pack(side='left', padx=(7, 0))
        ttk.Entry(row3, textvariable=self.prompt_text, width=14).pack(side='left', padx=3)
        ttk.Button(row3, text='Save draft', command=lambda: self.save('draft')).pack(side='left', padx=3)
        ttk.Button(row3, text='Approve + save', command=lambda: self.save('approved')).pack(side='left', padx=3)

        row4 = ttk.Frame(self, padding=(8, 3))
        row4.pack(fill='x')
        ttk.Label(row4, text='Overlay:').pack(side='left')
        ttk.Combobox(row4, textvariable=self.overlay_colour, width=10,
                     values=['Purple', 'Cyan', 'Green', 'Magenta'], state='readonly').pack(side='left', padx=4)
        self.overlay_colour.trace_add('write', lambda *_: self.request_render())
        ttk.Label(row4, text='Opacity').pack(side='left', padx=(6, 0))
        ttk.Scale(row4, from_=0.05, to=0.75, variable=self.opacity, length=90,
                  command=lambda _: self.request_render()).pack(side='left', padx=4)
        ttk.Checkbutton(row4, text='Cyan boundary', variable=self.show_edge,
                        command=self.request_render).pack(side='left', padx=8)
        ttk.Checkbutton(row4, text='Show candidate preview', variable=self.show_candidate,
                        command=self.request_render).pack(side='left', padx=7)
        ttk.Label(row4, text='SAM3 score ≥').pack(side='left', padx=(10, 2))
        ttk.Scale(row4, from_=0.1, to=0.9, variable=self.threshold, length=75).pack(side='left')
        ttk.Label(row4, text='Annotator:').pack(side='left', padx=(10, 1))
        ttk.Entry(row4, textvariable=self.annotator, width=13).pack(side='left')

        frame = ttk.Frame(self)
        frame.pack(fill='both', expand=True, padx=8, pady=5)
        self.canvas = tk.Canvas(frame, bg='#131923', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.picture_id = self.canvas.create_image(0, 0, anchor='nw')
        self.canvas.bind('<Configure>', lambda e: self.request_render())
        self.canvas.bind('<ButtonPress-1>', self.left_down)
        self.canvas.bind('<B1-Motion>', self.left_drag)
        self.canvas.bind('<ButtonRelease-1>', self.left_up)
        self.canvas.bind('<Double-Button-1>', self.double_click)
        self.canvas.bind('<Motion>', self.motion)
        self.canvas.bind('<Leave>', self.mouse_leave)
        self.canvas.bind('<ButtonPress-3>', self.pan_start)
        self.canvas.bind('<B3-Motion>', self.pan_move)
        self.canvas.bind('<ButtonRelease-3>', self.left_up)
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.bind('<Control-s>', lambda e: self.save('draft'))
        self.bind('<Control-z>', lambda e: self.undo())
        self.bind('<Escape>', lambda e: self.cancel_edit())
        self.bind('<Return>', lambda e: self.finish_polygon())
        self.bind('<Delete>', lambda e: self.remove_nearest_vertex())
        footer = ttk.Frame(self, padding=(8, 6))
        footer.pack(fill='x')
        ttk.Label(footer, textvariable=self.status).pack(side='left', padx=3)
        ttk.Label(footer, text='Wheel zoom | Right-drag pan | Red + / Blue − prompts | Esc cancel shape').pack(side='right')

    def _out(self):
        return self.folder / 'segment_studio_output'

    def _mask_path(self, image: Path):
        return self._out() / 'masks' / f'{image.stem}.png'

    def _sources(self, image: Path):
        return [self._mask_path(image),
                self.folder / 'firemask_output' / 'masks' / f'{image.stem}.png',
                self.folder / 'input_masks' / f'{image.stem}.png',
                self.folder / 'masks' / f'{image.stem}.png',
                self.folder / f'{image.stem}_mask.png']

    def _can_abandon(self):
        return not self.dirty or messagebox.askyesno('Unsaved edits', 'Discard unsaved edits to this image?')

    def open_folder(self):
        if self.busy or not self._can_abandon():
            return
        folder = filedialog.askdirectory(title='Choose RGB folder')
        if not folder:
            return
        self.folder = Path(folder)
        self.images = sorted((p for p in self.folder.iterdir() if is_rgb_image(p)), key=lambda p: p.name.lower())
        if not self.images:
            messagebox.showwarning('Empty folder', 'No RGB images found directly inside this folder.')
            return
        try:
            self.pairs = load_image_pairs(self.folder / 'image_pairs.csv')
        except Exception as exc:
            messagebox.showwarning('Invalid image_pairs.csv', str(exc))
            self.pairs = {}
        self.open_index(0)

    def choose_ir_folder(self):
        folder = filedialog.askdirectory(title='Choose optional IR folder')
        if folder:
            self.ir_folder = Path(folder)
            if self.image_path:
                self._load_ir_partner()
                self.request_render()

    def _load_ir_partner(self):
        self.ir_image = None
        if self.image_path is None:
            return
        partner = self.pairs.get(self.image_path.name)
        choices = []
        if partner:
            path = Path(partner)
            if path.is_absolute():
                choices.append(path)
            else:
                if self.ir_folder:
                    choices.append(self.ir_folder / path)
                choices.append(self.folder / path)
        elif self.ir_folder:
            stem = self.image_path.stem
            for suffix in ('_rgb', '_RGB', '_visible', '_VIS'):
                if stem.endswith(suffix):
                    stem = stem[:-len(suffix)]
                    break
            # Filename matching is a view-only convenience, NOT evidence of alignment.
            choices.extend(p for p in self.ir_folder.iterdir() if p.is_file()
                           and p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.tif', '.tiff')
                           and p.stem.lower() in (stem.lower(), stem.lower() + '_ir', stem.lower() + '_thermal'))
        for candidate in choices:
            if candidate.exists():
                try:
                    with Image.open(candidate) as im:
                        self.ir_image = im.convert('RGB').copy()
                    break
                except OSError:
                    pass

    def toggle_ir(self):
        if self.ir_preview.get() and self.ir_image is None:
            self.ir_preview.set(False)
            messagebox.showinfo('No paired IR image', 'No IR partner found. Use image_pairs.csv or select an IR folder.')
            return
        self.fit()
        if self.ir_preview.get():
            self.status.set('IR preview only: editing disabled. RGB–IR alignment is NOT assumed.')

    def navigate(self, shift):
        if not self.images or self.busy or not self._can_abandon():
            return
        self.open_index(max(0, min(self.idx + shift, len(self.images) - 1)))

    def open_index(self, index):
        path = self.images[index]
        try:
            with Image.open(path) as im:
                image = im.convert('RGB').copy()
            found = next((f for f in self._sources(path) if f.is_file()), None)
            mask = binary_mask(found, image.size) if found else Image.new('L', image.size, 0)
        except Exception as exc:
            messagebox.showerror('Cannot load image/mask', f'{path.name}\n{exc}')
            return
        self.idx = index
        self.image_path = path
        self.image = image
        self.mask = mask
        self.original_mask = mask.copy()
        self.dirty = False
        self.points.clear()
        self.undo_stack.clear()
        self.pending_candidate = None
        self.pending_model = None
        self.free_poly = []
        self.orig_contour = None
        self.orig_contour_full = None
        self.edit_contour = None
        self.base_before_edit = None
        self.ir_preview.set(False)
        self._load_ir_partner()
        self.mask_status = 'loaded' if found else 'unreviewed'
        self.source = f'existing mask ({found.parent.name})' if found else 'manual'
        self.image_label.set(path.name)
        self.counter.set(f'{index+1}/{len(self.images)}')
        self.status.set('Existing annotation loaded.' if found else 'New image. Annotate visible flames only.')
        self.fit()

    def fit(self):
        image = self._current_view_image()
        if image is None:
            return
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        self.scaling = min(cw / image.width, ch / image.height, 1.0)
        self.offset = ((cw - image.width * self.scaling) / 2,
                       (ch - image.height * self.scaling) / 2)
        self.request_render()

    def _current_view_image(self):
        return self.ir_image if self.ir_preview.get() and self.ir_image else self.image

    def request_render(self):
        if self.render_task is None:
            self.render_task = self.after(33, self._render)

    def _render(self):
        self.render_task = None
        image = self._current_view_image()
        if image is None:
            return
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        scale = max(0.001, self.scaling)
        ox, oy = self.offset
        x0 = max(0, min(image.width, int(math.floor(-ox / scale))))
        y0 = max(0, min(image.height, int(math.floor(-oy / scale))))
        x1 = max(0, min(image.width, int(math.ceil((cw - ox) / scale))))
        y1 = max(0, min(image.height, int(math.ceil((ch - oy) / scale))))
        base = np.empty((ch, cw, 3), dtype=np.uint8)
        base[:] = (19, 25, 35)
        if x1 > x0 and y1 > y0:
            dx0 = max(0, round(ox + x0 * scale))
            dy0 = max(0, round(oy + y0 * scale))
            dx1 = min(cw, round(ox + x1 * scale))
            dy1 = min(ch, round(oy + y1 * scale))
            # Keep an on-screen RGB layer cache: mask modifications only rebuild the overlay.
            key = (id(image), x0, y0, x1, y1, dx0, dy0, dx1, dy1)
            if key != self.cache_key:
                self.cache_key = key
                target_size = (max(1, dx1 - dx0), max(1, dy1 - dy0))
                self.cache_rgb = np.asarray(image.crop((x0, y0, x1, y1)).resize(target_size,
                                                     Image.Resampling.BILINEAR)).copy()
            if self.cache_rgb is not None:
                rh, rw = self.cache_rgb.shape[:2]
                region = base[dy0:dy0+rh, dx0:dx0+rw]
                if region.shape == self.cache_rgb.shape:
                    region[:] = self.cache_rgb
                    if not self.ir_preview.get() and self.mask is not None:
                        preview_size = (rw, rh)
                        occupied = np.asarray(self.mask.crop((x0, y0, x1, y1)).resize(
                            preview_size, Image.Resampling.NEAREST)) > 0
                        colours = {'Purple': (165, 40, 255), 'Cyan': (0, 240, 250),
                                   'Green': (0, 255, 110), 'Magenta': (245, 20, 200)}
                        colour = np.asarray(colours.get(self.overlay_colour.get(), (165, 40, 255)), dtype=float)
                        alpha = self.opacity.get()
                        if occupied.any():
                            region[occupied] = (region[occupied] * (1-alpha) + colour * alpha).astype(np.uint8)
                            if self.show_edge.get():
                                bits = occupied.astype(np.uint8)
                                kernel = np.ones((3, 3), dtype=np.uint8)
                                edges = cv2.morphologyEx(bits, cv2.MORPH_GRADIENT, kernel) > 0
                                region[edges] = (0, 255, 255)
                        if self.pending_candidate is not None and self.show_candidate.get():
                            cand = np.asarray(self.pending_candidate.crop((x0, y0, x1, y1)).resize(
                                preview_size, Image.Resampling.NEAREST)) > 0
                            if cand.any():
                                region[cand] = (0.6 * region[cand] + 0.4 * np.array([70, 255, 85])).astype(np.uint8)
                                border = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_GRADIENT,
                                                          np.ones((3, 3), np.uint8)) > 0
                                region[border] = (70, 255, 85)
        self.photo = ImageTk.PhotoImage(Image.fromarray(base, 'RGB'))
        self.canvas.itemconfig(self.picture_id, image=self.photo)
        self._render_annotations()

    def _render_annotations(self):
        self.canvas.delete('guide')
        if self.ir_preview.get():
            return
        for x, y, label in self.points:
            sx, sy = self.to_screen((x, y))
            color = '#ff5050' if label else '#43aaff'
            self.canvas.create_oval(sx-5, sy-5, sx+5, sy+5, fill=color,
                                    outline='white', width=2, tags='guide')
        outline = self.edit_contour if self.edit_contour is not None else self.free_poly
        if outline:
            pts = []
            for p in outline:
                pts.extend(self.to_screen(p))
            if len(outline) > 1:
                self.canvas.create_line(*pts, fill='#ffff66', width=2,
                                        tags='guide', smooth=False)
                if self.edit_contour is not None and len(outline) > 2:
                    sx,sy=self.to_screen(outline[0])
                    lx,ly=self.to_screen(outline[-1])
                    self.canvas.create_line(lx,ly,sx,sy,fill='#ffff66',width=2,tags='guide')
            for i, point in enumerate(outline):
                sx, sy = self.to_screen(point)
                r = 4 if self.edit_contour is not None else 3
                self.canvas.create_oval(sx-r,sy-r,sx+r,sy+r,
                                        fill='#ff7a55' if self.edit_contour is not None and i==self.selected_vertex else '#ffff66',
                                        outline='#171717',width=1,tags='guide')

    def to_screen(self, pos):
        return self.offset[0] + pos[0] * self.scaling, self.offset[1] + pos[1] * self.scaling

    def to_image(self, ev):
        if self.image is None:
            return None
        x = round((ev.x - self.offset[0]) / self.scaling)
        y = round((ev.y - self.offset[1]) / self.scaling)
        return (int(x), int(y)) if 0 <= x < self.image.width and 0 <= y < self.image.height else None

    def motion(self, ev):
        self.canvas.delete('cursor')
        if self.image is None or self.ir_preview.get():
            return
        if self.mode.get() in ('Paint fire', 'Erase'):
            radius = max(1, self.brush.get() * self.scaling / 2)
            self.canvas.create_oval(ev.x-radius, ev.y-radius, ev.x+radius, ev.y+radius,
                                    outline='#e9ff6a', width=1, tags='cursor')
        elif self.mode.get() == 'Edit boundary' and self.edit_contour is not None:
            self.canvas.configure(cursor='hand2')
        else:
            self.canvas.configure(cursor='crosshair')

    def mouse_leave(self, ev):
        self.canvas.delete('cursor')

    def _snapshot(self):
        if self.mask is not None:
            self.undo_stack.append(mask_pack(self.mask))
            if len(self.undo_stack) > MAX_UNDO:
                self.undo_stack.pop(0)

    def _paint(self, current, previous=None):
        if self.mask is None:
            return
        radius = max(1, round(self.brush.get() / 2))
        fill = 0 if self.mode.get() == 'Erase' else 255
        draw = ImageDraw.Draw(self.mask)
        if previous:
            draw.line([previous, current], width=radius*2, fill=fill, joint='curve')
        x,y=current
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=fill)
        self.dirty = True
        self.source = 'manual correction'
        self.request_render()

    def left_down(self, ev):
        if self.busy or self.ir_preview.get():
            return
        pos = self.to_image(ev)
        mode = self.mode.get()
        if mode == 'Pan':
            self.pan_last = (ev.x, ev.y)
            return
        if pos is None:
            return
        if mode in ('Paint fire', 'Erase'):
            if self.orig_contour is not None:
                self.status.set('Commit or cancel the boundary edit before painting.')
                return
            self._snapshot()
            self.drag_last = pos
            self._paint(pos)
        elif mode in ('SAM positive','SAM negative'):
            self.points.append((*pos, 1 if mode == 'SAM positive' else 0))
            self.status.set(f'{len(self.points)} points. Run candidate to refine; SAM2 reuses image embedding.')
            self.request_render()
        elif mode in ('Polygon add','Polygon erase'):
            self.free_poly.append(pos)
            self.status.set(f'{len(self.free_poly)} polygon points. Click Finish polygon or press Enter.')
            self.request_render()
        elif mode == 'Edit boundary':
            if self.edit_contour is None:
                self.select_contour(pos)
            else:
                if ev.state & 0x0001:  # Shift-click inserts a new vertex on closest polygon edge.
                    index=self._nearest_edge_insert_index(ev.x,ev.y)
                    if index is not None:
                        self.edit_contour.insert(index,pos)
                        self.selected_vertex=index
                        self.request_render()
                else:
                    match = self._nearest_vertex(ev.x, ev.y)
                    if match is not None:
                        self.vertex_drag = match
                        self.selected_vertex=match
                        self.request_render()

    def left_drag(self, ev):
        if self.busy or self.ir_preview.get():
            return
        mode=self.mode.get()
        if mode == 'Pan' and self.pan_last is not None:
            self._pan(ev)
        elif mode in ('Paint fire','Erase') and self.drag_last is not None:
            pos=self.to_image(ev)
            if pos is not None:
                self._paint(pos, self.drag_last)
                self.drag_last=pos
        elif mode == 'Edit boundary' and self.vertex_drag is not None:
            pos=self.to_image(ev)
            if pos:
                self.edit_contour[self.vertex_drag]=pos
                self._render_annotations()

    def left_up(self, ev):
        self.drag_last=None
        self.pan_last=None
        self.vertex_drag=None

    def double_click(self, ev):
        if self.mode.get() in ('Polygon add','Polygon erase'):
            self.finish_polygon()

    def _nearest_vertex(self, x, y):
        if self.edit_contour is None:
            return None
        distance, index = min(((math.hypot(x-sx,y-sy),i) for i,p in enumerate(self.edit_contour)
                               for sx,sy in [self.to_screen(p)]),default=(1e9,None))
        return index if distance<=14 else None

    def _nearest_edge_insert_index(self, x, y):
        if self.edit_contour is None:
            return None
        edges=[]
        for idx in range(len(self.edit_contour)):
            a=self.to_screen(self.edit_contour[idx])
            b=self.to_screen(self.edit_contour[(idx+1)%len(self.edit_contour)])
            vx,vy=b[0]-a[0],b[1]-a[1]
            denom=vx*vx+vy*vy
            t=max(0,min(1,((x-a[0])*vx+(y-a[1])*vy)/denom)) if denom else 0
            d=math.hypot(x-(a[0]+t*vx),y-(a[1]+t*vy))
            edges.append((d,(idx+1)%len(self.edit_contour)))
        dist,index=min(edges)
        return index if dist<=18 else None

    def remove_nearest_vertex(self):
        if self.edit_contour is not None and self.selected_vertex is not None:
            if len(self.edit_contour)>3:
                self.edit_contour.pop(self.selected_vertex)
                self.vertex_drag=None
                self.selected_vertex=None
                self.request_render()

    def select_contour(self, pos):
        if self.mask is None:
            return
        tolerance=max(6,20/self.scaling)
        polygon=detect_component_polygon(self.mask,pos,tolerance_px=tolerance,
                                         simplify_px=max(2,1.8/self.scaling),max_vertices=180,return_full=True)
        if polygon is None:
            self.status.set('No boundary found near click; select a visible masked region, then drag yellow nodes.')
            return
        simplified, full = polygon
        self.orig_contour=simplified.copy()
        self.orig_contour_full=full
        self.edit_contour=simplified.copy()
        self.base_before_edit=self.mask.copy()
        self.selected_vertex=None
        self.status.set(f'{len(simplified)} vertices. Drag a point; Shift-click a line to add; Delete selected point; Commit boundary. Fine edges may simplify.')
        self.request_render()

    def commit_boundary(self):
        if self.orig_contour is None or self.edit_contour is None:
            return
        self._snapshot()
        self.mask=replace_polygon_component(self.base_before_edit,self.orig_contour_full,self.edit_contour)
        self.dirty=True
        self.source='boundary vertex correction'
        self.orig_contour=self.orig_contour_full=self.edit_contour=self.base_before_edit=None
        self.status.set('Boundary change applied. Save draft to keep it.')
        self.request_render()

    def finish_polygon(self):
        if self.mask is None or len(self.free_poly)<3 or self.busy:
            return
        coords=[]
        for p in self.free_poly:
            if not coords or p!=coords[-1]:
                coords.append(p)
        if len(coords)<3:
            return
        self._snapshot()
        ImageDraw.Draw(self.mask).polygon(coords,fill=255 if self.mode.get()=='Polygon add' else 0)
        self.free_poly=[]
        self.dirty=True
        self.source='manual polygon correction'
        self.status.set('Polygon applied; save when satisfied.')
        self.request_render()

    def cancel_edit(self):
        self.free_poly=[]
        self.orig_contour=self.orig_contour_full=self.edit_contour=self.base_before_edit=None
        self.vertex_drag=None
        self.selected_vertex=None
        self.status.set('Temporary edit cancelled; saved mask unchanged.')
        self.request_render()

    def pan_start(self, ev):
        self.pan_last=(ev.x,ev.y)

    def _pan(self, ev):
        dx=ev.x-self.pan_last[0]
        dy=ev.y-self.pan_last[1]
        self.pan_last=(ev.x,ev.y)
        self.offset=(self.offset[0]+dx,self.offset[1]+dy)
        self.request_render()

    def pan_move(self, ev):
        if self.pan_last is not None:
            self._pan(ev)

    def wheel(self, ev):
        image=self._current_view_image()
        if image is None:
            return
        old=self.scaling
        new=min(6.0,max(0.015,old*(1.23 if ev.delta>0 else 1/1.23)))
        ix=(ev.x-self.offset[0])/old
        iy=(ev.y-self.offset[1])/old
        self.scaling=new
        self.offset=(ev.x-ix*new,ev.y-iy*new)
        self.request_render()

    def undo(self):
        if self.busy or not self.undo_stack:
            return
        self.cancel_edit()
        self.mask=mask_unpack(self.undo_stack.pop())
        self.dirty=True
        self.source='manual correction (undo)'
        self.request_render()

    def clear_mask(self):
        if self.mask is not None and not self.busy and not self.ir_preview.get():
            if messagebox.askyesno('Clear mask','Clear current working mask? Undo is available; saved files remain unchanged.'):
                self._snapshot()
                self.mask=Image.new('L',self.mask.size,0)
                self.dirty=True
                self.request_render()

    def clear_prompts(self):
        self.points.clear()
        self.request_render()

    def run_candidate(self):
        if self.busy or self.image is None or self.ir_preview.get():
            return
        variant=self.model.get()
        if variant.startswith('SAM2') and not any(p[2] for p in self.points):
            messagebox.showinfo('Positive clicks required','Place one or more positive points on visible fire before running SAM2.')
            return
        self.busy=True
        self.pending_candidate=None
        path=self.image_path
        points=self.points.copy()
        prompt=self.prompt_text.get().strip() or 'flames'
        threshold=float(self.threshold.get())
        self.status.set(f'Running {variant}. SAM2 image embedding cached per model/image; SAM3 may require more VRAM.')
        threading.Thread(target=self._candidate_thread,
                         args=(variant,self.image,path,points,prompt,threshold),daemon=True).start()

    def _candidate_thread(self,variant,image,path,points,prompt,threshold):
        try:
            if variant == 'Colour demo (not AI)':
                answer=colour_candidate(image)
            elif variant.startswith('SAM2'):
                answer=self.sam2.predict(variant,image,points,str(path.resolve()))
            elif variant == 'SAM3 text':
                self.sam2.clear()  # Do not keep both full models on an 8 GB GPU.
                answer=sam3_predict(path,prompt,threshold)
            else:
                raise ValueError(f'Unknown model choice: {variant}')
            self.running_queue.put(('ok',answer,variant,path))
        except Exception:
            self.running_queue.put(('error',traceback.format_exc(),variant,path))

    def _check_queue(self):
        while not self.running_queue.empty():
            result,value,variant,path=self.running_queue.get_nowait()
            self.busy=False
            if path != self.image_path:
                continue
            if result=='error':
                self.status.set(f'{variant} failed. Existing mask preserved.')
                messagebox.showerror('Model inference failed',value[-4500:])
            else:
                if value.size != self.mask.size:
                    self.status.set('Candidate discarded because dimensions differ.')
                    messagebox.showerror('Size mismatch','Candidate must have the same dimensions as the RGB image.')
                else:
                    self.pending_candidate=value
                    self.pending_model=variant
                    self.show_candidate.set(True)
                    self.status.set(f'{variant} candidate ready (GREEN). Choose Apply as, then Apply candidate. Your current mask is unchanged.')
                    self.request_render()
        self.after(120,self._check_queue)

    def apply_candidate(self):
        if self.pending_candidate is None or self.mask is None or self.busy or self.ir_preview.get():
            return
        self._snapshot()
        self.mask=merge_masks(self.mask,self.pending_candidate,self.merge.get())
        self.source=f'{self.pending_model}: {self.merge.get()}'
        self.pending_candidate=None
        self.pending_model=None
        self.dirty=True
        self.status.set('Candidate applied; manually correct or add more SAM prompts, then save.')
        self.request_render()

    def discard_candidate(self):
        self.pending_candidate=None
        self.pending_model=None
        self.status.set('Candidate discarded. Existing mask unchanged.')
        self.request_render()

    def save(self,status):
        if self.busy or self.image_path is None or self.mask is None or self.folder is None:
            return
        if self.ir_preview.get():
            messagebox.showinfo('Switch to RGB','Return to RGB view before saving RGB annotations.')
            return
        if self.orig_contour is not None or self.free_poly:
            messagebox.showinfo('Finish edit','Commit or cancel the current polygon/boundary edit first.')
            return
        if self.pending_candidate is not None:
            if not messagebox.askyesno('Candidate not applied','There is an unapplied candidate. Save current edited mask WITHOUT the candidate?'):
                return
        try:
            mask_file=self._mask_path(self.image_path)
            save_png_atomic(self.mask,mask_file)
            out=self._out()
            preview_dir=out/'overlays'
            preview_dir.mkdir(parents=True,exist_ok=True)
            # Preview is a visual reference only; label image remains 0/255 grayscale.
            thumb=self.image.copy()
            thumb.thumbnail((1600,1600))
            mm=self.mask.resize(thumb.size,Image.Resampling.NEAREST)
            rgba=thumb.convert('RGBA')
            top=Image.new('RGBA',thumb.size,(165,40,255,0))
            top.putalpha(mm.point(lambda p:80 if p else 0))
            preview=Image.alpha_composite(rgba,top).convert('RGB')
            preview.save(preview_dir/(self.image_path.stem+'_overlay.jpg'),quality=87)
            data={'image_file':self.image_path.name,
                  'mask_file':str(mask_file.relative_to(self.folder)).replace('\\','/'),
                  'width':self.image.width,'height':self.image.height,
                  'class_id':1,'class_name':'visible_flame',
                  'definition':'Only flames directly visible in RGB; smoke and obscured fire excluded',
                  'status':status,'annotator':self.annotator.get().strip(),
                  'source':self.source,'updated_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  'flame_fraction':round(float(np.mean(np.asarray(self.mask)>0)),7),
                  'num_sam_prompts':len(self.points),'ir_paired':bool(self.ir_image is not None),
                  'ir_mask_inferred':False,'application':'Segment Studio'}
            metadata=out/'metadata'
            metadata.mkdir(parents=True,exist_ok=True)
            (metadata/(self.image_path.stem+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
            write_manifest(metadata,out/'annotation_manifest.csv')
            self.original_mask=self.mask.copy()
            self.dirty=False
            self.mask_status=status
            self.status.set(f'{status.title()} saved: {mask_file}. Source imagery untouched.')
        except Exception as exc:
            messagebox.showerror('Failed to save annotation',str(exc))


if __name__=='__main__':
    FireAnnotator().mainloop()
