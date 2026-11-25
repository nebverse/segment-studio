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
                        colour_candidate, detect_component_polygon,
                        save_png_atomic, write_manifest, load_image_pairs, apply_boundary_delta)
from sam_backends import Sam2Local, SAM2_CONFIGS, sam3_predict
from roi_utils import FULL, CROP, BOX, SCOPES, padded_roi, make_roi, validate_roi, scoped_points, run_scoped, merge_scoped

ROOT = Path(__file__).resolve().parent
MAX_UNDO = 10


class FireAnnotator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Segment Studio | Annotation workspace')
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
        self.pending_roi = None
        self.pending_scope = FULL
        self.pending_context = 0
        self.context_percent = tk.StringVar(value="10")
        self.image_generation = 0
        self.roi = None
        self.roi_start = None
        self.roi_preview = None
        self.scope = tk.StringVar(value=FULL)
        self.roi_label = tk.StringVar(value='No ROI selected')
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
        self.vertex_action = tk.StringVar(value='Move')
        self.vertex_history = []
        self.vertex_label = tk.StringVar(value='Select a masked flame to edit its boundary.')
        self.brush_label = tk.StringVar(value='14 px')
        self.score_label = tk.StringVar(value='0.40')
        self.mask_label = tk.StringVar(value='No image')
        self.candidate_label = tk.StringVar(value='No candidate')
        self.zoom_label = tk.StringVar(value='100%')
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
        self.model.trace_add('write', self._model_changed)
        self._update_roi_label()
        self.protocol('WM_DELETE_WINDOW', self._close_window)
        self.after(120, self._check_queue)

    def _build_ui(self):
        # Built-in ttk theme only: no Qt, customtkinter or extra packages.
        bg, panel, ink, muted, blue = '#edf1f6', '#ffffff', '#202d40', '#53657a', '#2365c5'
        self.configure(bg=bg)
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background=panel, foreground=ink)
        style.configure('TFrame', background=panel)
        style.configure('TLabel', background=panel, foreground=ink)
        style.configure('Muted.TLabel', foreground=muted, font=('Segoe UI', 9))
        style.configure('Section.TLabel', foreground=ink, font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', padding=(7, 5), background='#f1f5f9', bordercolor='#d5dfe9', relief='flat')
        style.map('TButton', background=[('disabled','#eef1f4'),('pressed','#d5e3f5'),('active','#e0ebf9')], foreground=[('disabled','#8290a0')])
        style.configure('Accent.TButton', background=blue, foreground='white', bordercolor=blue)
        style.map('Accent.TButton', background=[('disabled','#d8e0eb'),('pressed','#174c9d'),('active','#3177d8')], foreground=[('disabled','#8290a0'),('!disabled','white')])
        style.configure('Approve.TButton', background='#087c69', foreground='white', bordercolor='#087c69')
        style.map('Approve.TButton', background=[('disabled','#d8e0eb'),('pressed','#075b50'),('active','#0b907b')], foreground=[('disabled','#8290a0'),('!disabled','white')])
        style.configure('TCombobox', padding=3, fieldbackground='#f8fafc', bordercolor='#cbd6e1', arrowsize=12)
        style.map('TCombobox', fieldbackground=[('readonly','#f8fafc'),('disabled','#e9edf2')], selectbackground=[('readonly','#f8fafc')], selectforeground=[('readonly',ink)])
        style.configure('TEntry', padding=3, fieldbackground='#f8fafc', bordercolor='#cbd6e1')
        style.configure('TNotebook', background=bg, borderwidth=0, tabmargins=(0,0,0,0))
        style.configure('TNotebook.Tab', padding=(12,8), background='#e2e8f0', foreground=muted)
        style.map('TNotebook.Tab', background=[('selected',panel)], foreground=[('selected',blue)])
        style.configure('Header.TFrame', background='#17283e')
        style.configure('Header.TLabel', background='#17283e', foreground='#ffffff', font=('Segoe UI', 15, 'bold'))
        style.configure('HeaderInfo.TLabel', background='#17283e', foreground='#c4d3e6', font=('Segoe UI', 9))
        style.configure('TRadiobutton', background=panel)
        style.configure('TCheckbutton', background=panel)
        style.configure('Horizontal.TProgressbar', background=blue, troughcolor='#dce5ef')

        header = ttk.Frame(self, style='Header.TFrame', padding=(14,9)); header.pack(fill='x')
        ttk.Label(header, text='Segment Studio', style='Header.TLabel').pack(side='left')
        ttk.Label(header, text='Visible flame annotation', style='HeaderInfo.TLabel').pack(side='left', padx=12)
        ttk.Button(header, text='Open RGB folder', command=self.open_folder).pack(side='right', padx=(8,0))
        ttk.Button(header, text='IR folder', command=self.choose_ir_folder).pack(side='right')
        nav = ttk.Frame(self, padding=(10,5)); nav.pack(fill='x', pady=(0,1))
        ttk.Button(nav, text='Previous', command=lambda: self.navigate(-1)).pack(side='left')
        ttk.Label(nav, textvariable=self.counter, width=7, anchor='center').pack(side='left')
        ttk.Button(nav, text='Next', command=lambda: self.navigate(1)).pack(side='left')
        ttk.Label(nav, textvariable=self.image_label).pack(side='left', padx=12)
        ttk.Label(nav, textvariable=self.zoom_label, style='Muted.TLabel').pack(side='right', padx=8)
        ttk.Button(nav, text='Fit image', command=self.fit).pack(side='right')

        footer = ttk.Frame(self, padding=(10,6)); footer.pack(side='bottom', fill='x')
        self.status_display = ttk.Label(footer, textvariable=self.status, wraplength=880)
        self.status_display.pack(anchor='w', fill='x')
        ttk.Label(footer, textvariable=self.mode, style='Section.TLabel').pack(side='right',anchor='e',padx=5)
        ttk.Label(footer, text='Wheel: zoom   |   Right-drag: pan   |   Ctrl+S: draft   |   Ctrl+Z: undo   |   Esc: cancel edit', style='Muted.TLabel').pack(anchor='w')
        footer.bind('<Configure>', lambda e: self.status_display.configure(wraplength=max(300,e.width-24)))
        body = ttk.Frame(self); body.pack(fill='both', expand=True, padx=8, pady=6)
        sidebar = ttk.Frame(body, width=334); sidebar.pack(side='left', fill='y', padx=(0,8)); sidebar.pack_propagate(False)
        savebar = ttk.Frame(sidebar, padding=(10,8)); savebar.pack(side='bottom', fill='x')
        ttk.Separator(savebar).pack(fill='x', pady=(0,7))
        ttk.Label(savebar, textvariable=self.mask_label, style='Section.TLabel').pack(anchor='w')
        ttk.Label(savebar, textvariable=self.candidate_label, style='Muted.TLabel', wraplength=295).pack(anchor='w', pady=(2,5))
        self.progress = ttk.Progressbar(savebar, mode='determinate', length=290, maximum=100)
        self.progress.pack(fill='x', pady=(0,5))
        actions=ttk.Frame(savebar); actions.pack(fill='x')
        self.draft_button=ttk.Button(actions,text='Save draft',command=lambda:self.save('draft'))
        self.draft_button.pack(side='left',fill='x',expand=True,padx=(0,4))
        self.approve_button=ttk.Button(actions,text='Approve + save',style='Approve.TButton',command=lambda:self.save('approved'))
        self.approve_button.pack(side='left',fill='x',expand=True)
        ttk.Label(savebar,text='Annotator',style='Muted.TLabel').pack(anchor='w',pady=(6,0))
        ttk.Entry(savebar,textvariable=self.annotator).pack(fill='x')

        self.tabs=ttk.Notebook(sidebar); self.tabs.pack(fill='both',expand=True)
        # Scrollable pages prevent clipped controls at minimum window height / high DPI.
        def page(title):
            outer=ttk.Frame(self.tabs); self.tabs.add(outer,text=title)
            scroll=tk.Canvas(outer,bg=panel,highlightthickness=0,width=290)
            bar=ttk.Scrollbar(outer,orient='vertical',command=scroll.yview)
            bar.pack(side='right',fill='y'); scroll.pack(side='left',fill='both',expand=True)
            scroll.configure(yscrollcommand=bar.set)
            content=ttk.Frame(scroll,padding=(10,9)); window=scroll.create_window(0,0,anchor='nw',window=content)
            content.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
            scroll.bind('<Configure>',lambda e:scroll.itemconfigure(window,width=e.width))
            # Bind wheel to the page and its children, leaving the image wheel untouched.
            def wheel(e):
                scroll.yview_scroll(-1 if getattr(e,'delta',0)>0 or getattr(e,'num',0)==4 else 1,'units')
                return 'break'
            scroll.bind('<MouseWheel>',wheel); scroll.bind('<Button-4>',wheel); scroll.bind('<Button-5>',wheel)
            content.bind('<MouseWheel>',wheel); content.bind('<Button-4>',wheel); content.bind('<Button-5>',wheel)
            # Widgets created later share page scrolling, including comboboxes.
            def bind_children(parent):
                for child in parent.winfo_children():
                    for seq in ('<MouseWheel>','<Button-4>','<Button-5>'): child.bind(seq,wheel,add='+')
                    bind_children(child)
            self.after_idle(lambda:bind_children(content))
            return outer,content
        self.segment_tab,seg=page('Segment'); self.edit_tab,edit=page('Edit'); self.view_tab,view=page('View')
        def heading(parent,text):
            ttk.Label(parent,text=text,style='Section.TLabel').pack(anchor='w',pady=(8,3))
        def note(parent,text):
            ttk.Label(parent,text=text,style='Muted.TLabel',wraplength=264,justify='left').pack(anchor='w',pady=(2,5))
        def buttons(parent,items):
            row=ttk.Frame(parent); row.pack(fill='x',pady=2)
            for text,cmd in items: ttk.Button(row,text=text,command=cmd,width=0).pack(side='left',fill='x',expand=True,padx=2)
            return row
        def combo(parent,var,values):
            w=ttk.Combobox(parent,textvariable=var,values=values,state='readonly'); w.pack(fill='x',pady=(0,3)); return w

        heading(seg,'01  Model and inference area')
        self.model_box=combo(seg,self.model,[*SAM2_CONFIGS,'SAM3 text','Colour demo (not AI)'])
        self.scope_box=combo(seg,self.scope,SCOPES); self.scope_box.bind('<<ComboboxSelected>>',self._scope_changed)
        buttons(seg,[('Draw ROI',self.start_roi),('Fit ROI',self.fit_roi),('Clear ROI',self.clear_roi)])
        ttk.Label(seg,textvariable=self.roi_label,style='Muted.TLabel',wraplength=265).pack(anchor='w')
        row=ttk.Frame(seg); row.pack(fill='x',pady=2)
        ttk.Label(row,text='Crop context %').pack(side='left')
        self.context_box=ttk.Combobox(row,textvariable=self.context_percent,width=5,state='readonly',values=('0','5','10','20','30','50'))
        self.context_box.pack(side='right'); self.context_box.bind('<<ComboboxSelected>>',self._context_changed)
        heading(seg,'02  Model prompts')
        self.sam2_options=ttk.Frame(seg); self.sam2_options.pack(fill='x')
        buttons(self.sam2_options,[('Positive +',lambda:self._set_tool('SAM positive')),('Negative −',lambda:self._set_tool('SAM negative')),('Clear',self.clear_prompts)])
        note(self.sam2_options,'Click flames (+) or background (−). ROI can run without points.')
        self.sam3_options=ttk.Frame(seg); self.sam3_options.pack(fill='x')
        ttk.Label(self.sam3_options,text='SAM3 text',style='Muted.TLabel').pack(anchor='w')
        ttk.Entry(self.sam3_options,textvariable=self.prompt_text).pack(fill='x')
        row=ttk.Frame(self.sam3_options); row.pack(fill='x',pady=2)
        ttk.Label(row,text='Score ≥').pack(side='left')
        ttk.Scale(row,from_=0.1,to=0.9,variable=self.threshold,command=lambda v:self.score_label.set(f'{float(v):.2f}')).pack(side='left',fill='x',expand=True,padx=5)
        ttk.Label(row,textvariable=self.score_label,width=4).pack(side='right')
        self.colour_options=ttk.Frame(seg); self.colour_options.pack(fill='x'); note(self.colour_options,'RGB colour filter; no model weights required.')
        # Keep the prediction/merge actions visible even when options scroll.
        segment_actions=ttk.Frame(self.segment_tab,padding=(10,5))
        first_packed=self.segment_tab.pack_slaves()[0]
        segment_actions.pack(side='bottom',fill='x',before=first_packed)
        ttk.Separator(segment_actions).pack(fill='x',pady=(0,4))
        self.run_button=ttk.Button(segment_actions,text='Run candidate',style='Accent.TButton',command=self.run_candidate); self.run_button.pack(fill='x',pady=(0,3))
        heading(segment_actions,'03  Review and merge')
        combo(segment_actions,self.merge,['Replace','Add (union)','Subtract','Intersect'])
        row=ttk.Frame(segment_actions); row.pack(fill='x',pady=2)
        self.apply_button=ttk.Button(row,text='Apply candidate',style='Accent.TButton',command=self.apply_candidate); self.apply_button.pack(side='left',expand=True,fill='x',padx=(0,3))
        self.discard_button=ttk.Button(row,text='Discard',command=self.discard_candidate); self.discard_button.pack(side='left',expand=True,fill='x')
        note(segment_actions,'Green = pending; apply to keep.')

        heading(edit,'Manual annotation')
        self.tool_box=combo(edit,self.mode,['Paint fire','Erase','SAM positive','SAM negative','Polygon add','Polygon erase','Edit boundary','Draw ROI','Pan'])
        row=ttk.Frame(edit); row.pack(fill='x',pady=3)
        ttk.Label(row,text='Brush').pack(side='left'); ttk.Scale(row,from_=2,to=120,variable=self.brush,command=lambda v:self.brush_label.set(f'{round(float(v))} px')).pack(side='left',fill='x',expand=True,padx=5); ttk.Label(row,textvariable=self.brush_label,width=6).pack(side='right')
        buttons(edit,[('Finish polygon',self.finish_polygon),('Undo (Ctrl+Z)',self.undo)])
        heading(edit,'Boundary vertices')
        ttk.Button(edit,text='Select / edit boundary',command=lambda:self._set_tool('Edit boundary'),style='Accent.TButton').pack(fill='x',pady=2)
        self.vertex_controls=ttk.Frame(edit); self.vertex_controls.pack(fill='x')
        row=ttk.Frame(self.vertex_controls); row.pack(fill='x',pady=3)
        self.vertex_radios=[]
        for v in ('Move','Add','Remove'):
            w=ttk.Radiobutton(row,text=v,value=v,variable=self.vertex_action,command=self._vertex_action_changed); w.pack(side='left',expand=True); self.vertex_radios.append(w)
        ttk.Label(self.vertex_controls,textvariable=self.vertex_label,style='Muted.TLabel',wraplength=264,justify='left').pack(anchor='w',pady=(2,4))
        row=ttk.Frame(self.vertex_controls); row.pack(fill='x',pady=2)
        self.vertex_delete=ttk.Button(row,text='Delete selected',command=self.remove_nearest_vertex); self.vertex_delete.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.vertex_undo=ttk.Button(row,text='Undo vertex',command=self.undo_vertex); self.vertex_undo.pack(side='left',fill='x',expand=True)
        row=ttk.Frame(edit); row.pack(fill='x',pady=3)
        self.commit_button=ttk.Button(row,text='Commit boundary',style='Approve.TButton',command=self.commit_boundary); self.commit_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        ttk.Button(row,text='Cancel edit',command=self.cancel_edit).pack(side='left',fill='x',expand=True)
        note(edit,'Shift-click an edge to add. Select a node, then Delete to remove. Commit when satisfied.')
        heading(edit,'Mask actions')
        ttk.Button(edit,text='Clear working mask',command=self.clear_mask).pack(fill='x')

        heading(view,'Image and overlay')
        ttk.Checkbutton(view,text='View IR only (read-only)',variable=self.ir_preview,command=self.toggle_ir).pack(anchor='w',pady=3)
        combo(view,self.overlay_colour,['Purple','Cyan','Green','Magenta'])
        self.overlay_colour.trace_add('write',lambda *_:self.request_render())
        ttk.Label(view,text='Overlay opacity').pack(anchor='w'); ttk.Scale(view,from_=0.05,to=0.75,variable=self.opacity,command=lambda _:self.request_render()).pack(fill='x')
        ttk.Checkbutton(view,text='Cyan boundary',variable=self.show_edge,command=self.request_render).pack(anchor='w',pady=3)
        ttk.Checkbutton(view,text='Show candidate preview',variable=self.show_candidate,command=self.request_render).pack(anchor='w',pady=3)
        buttons(view,[('Fit image',self.fit),('Fit ROI',self.fit_roi)])
        note(view,'Right-drag to pan; wheel to zoom. IR is a reference only; RGB–IR alignment is not assumed.')
        heading(view,'Overlay legend')
        note(view,'Purple (default): accepted mask\nGreen: pending candidate\nAmber: ROI   |   Blue: context\nYellow: editable boundary vertices')

        frame=ttk.Frame(body); frame.pack(side='left',fill='both',expand=True)
        self.canvas=tk.Canvas(frame,bg='#131923',highlightthickness=0,cursor='crosshair',takefocus=True)
        self.canvas.pack(fill='both',expand=True)
        self.picture_id=self.canvas.create_image(0,0,anchor='nw')
        self.canvas.create_text(24,24,anchor='nw',text='Open an RGB folder to begin',fill='#b5c3d6',font=('Segoe UI',14),tags='welcome')
        self.canvas.bind('<Configure>',lambda e:self.request_render())
        for sequence,handler in [('<ButtonPress-1>',self.left_down),('<B1-Motion>',self.left_drag),('<ButtonRelease-1>',self.left_up),('<Double-Button-1>',self.double_click),('<Motion>',self.motion),('<Leave>',self.mouse_leave),('<ButtonPress-3>',self.pan_start),('<B3-Motion>',self.pan_move),('<ButtonRelease-3>',self._pan_end),('<MouseWheel>',self.wheel),('<Button-4>',self.wheel),('<Button-5>',self.wheel)]:
            self.canvas.bind(sequence,handler)
        self.bind('<Control-s>',lambda e:self.save('draft'))
        self.bind('<Control-z>',self._keyboard_undo)
        self.bind('<Escape>',lambda e:self.cancel_edit())
        self.bind('<Control-r>',lambda e:self.start_roi())
        self.bind('<Return>',self._keyboard_enter)
        self.bind('<Delete>',self._keyboard_delete)
        self._last_mode=self.mode.get()
        self.mode.trace_add('write',self._tool_changed)
        self.ir_preview.trace_add('write',lambda *_:self._refresh_ui())
        self._model_options()
        self._refresh_ui()

    def _set_tool(self, mode):
        self.mode.set(mode)
        if self.mode.get()==mode:
            self.canvas.focus_set()
            if mode=='Edit boundary' and self.edit_contour is None:
                self.status.set('Click an accepted flame mask to select its boundary.')

    def _tool_changed(self, *_):
        mode=self.mode.get()
        if mode==self._last_mode: return
        if self.free_poly or self.edit_contour is not None or self.roi_start is not None:
            self.mode.set(self._last_mode)
            self.status.set('Commit or cancel the current shape before changing tools.')
            return
        self._last_mode=mode
        self.vertex_action.set('Move')
        if mode=='Edit boundary': self.tabs.select(self.edit_tab)
        self.canvas.configure(cursor='crosshair')
        self._refresh_ui()

    def _model_options(self):
        for w in (self.sam2_options,self.sam3_options,self.colour_options): w.pack_forget()
        w=self.sam2_options if self.model.get().startswith('SAM2') else self.sam3_options if self.model.get()=='SAM3 text' else self.colour_options
        w.pack(fill='x')

    def _refresh_ui(self):
        if not hasattr(self,'draft_button') or not hasattr(self,'canvas'): return
        ready=self.image is not None and not self.busy and not self.ir_preview.get()
        active=self.edit_contour is not None
        shape=active or bool(self.free_poly) or self.roi_start is not None
        pending=self.pending_candidate is not None
        def state(w,enabled): w.configure(state='normal' if enabled else 'disabled')
        for w in (self.draft_button,self.approve_button,self.run_button): state(w,ready and not shape)
        state(self.apply_button,ready and pending and not shape); state(self.discard_button,ready and pending)
        for w in self.vertex_radios: state(w,ready and active)
        state(self.vertex_delete,ready and active and self.selected_vertex is not None and len(self.edit_contour)>3)
        state(self.vertex_undo,ready and active and bool(self.vertex_history))
        state(self.commit_button,ready and active)
        self.mask_label.set('No image' if self.image is None else ('Working mask · unsaved' if self.dirty else f'Mask · {self.mask_status}'))
        self.candidate_label.set('Inference running…' if self.busy else f'Pending · {self.pending_scope} · {self.pending_model or "model"}' if pending else 'No pending candidate')
        self.zoom_label.set(f'{self.scaling*100:.0f}%')
        if self.busy and not getattr(self,'_progress_running',False): self.progress.configure(mode='indeterminate'); self.progress.start(14); self._progress_running=True
        elif not self.busy and getattr(self,'_progress_running',False): self.progress.stop(); self.progress.configure(mode='determinate',value=0); self._progress_running=False
        if active:
            hint={'Move':'Drag a node to move it.','Add':'Click near an edge to insert a node.','Remove':'Click a node to delete it.'}[self.vertex_action.get()]
            self.vertex_label.set(f'{len(self.edit_contour)} vertices · {hint}')
        else: self.vertex_label.set('Select a masked flame to edit its boundary.')

    def _keyboard_undo(self, ev):
        if isinstance(ev.widget,(tk.Entry,ttk.Entry,ttk.Combobox)): return
        self.undo(); return 'break'

    def _keyboard_enter(self, ev):
        if isinstance(ev.widget,(tk.Entry,ttk.Entry,ttk.Combobox,ttk.Button)): return
        if self.edit_contour is not None: self.commit_boundary()
        else: self.finish_polygon()
        return 'break'

    def _keyboard_delete(self, ev):
        if isinstance(ev.widget,(tk.Entry,ttk.Entry,ttk.Combobox)): return
        self.remove_nearest_vertex(); return 'break'

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
        if self.free_poly or self.edit_contour is not None or self.roi_start is not None:
            if not messagebox.askyesno('Uncommitted shape','Leave and discard the temporary shape?',default='no'): return False
        if self.pending_candidate is not None:
            return messagebox.askyesno('Unapplied candidate',
                'Leave this image and discard the green candidate and any unsaved edits?\n'
                'Choose No to return, apply the candidate and save.', default='no')
        return not self.dirty or messagebox.askyesno('Unsaved edits', 'Discard unsaved edits to this image?', default='no')

    def _close_window(self):
        if self.busy:
            messagebox.showinfo('Inference running', 'Finish inference before closing Segment Studio.')
            return
        if self._can_abandon():
            self.destroy()

    def open_folder(self):
        if self.busy or not self._can_abandon():
            return
        folder = filedialog.askdirectory(title='Choose RGB folder')
        if not folder:
            return
        new_folder=Path(folder)
        new_images=sorted((p for p in new_folder.iterdir() if is_rgb_image(p)),key=lambda p:p.name.lower())
        if not new_images:
            messagebox.showwarning('Empty folder', 'No RGB images found directly inside this folder.')
            return
        self.folder,self.images=new_folder,new_images
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
        if self.ir_preview.get() and (self.free_poly or self.edit_contour is not None or self.roi_start is not None):
            self.ir_preview.set(False)
            self.status.set('Commit or cancel the current shape before switching to IR.')
            return
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
        self.image_generation += 1
        self.mask = mask
        self.original_mask = mask.copy()
        self.dirty = False
        self.points.clear()
        self.undo_stack.clear()
        self.pending_candidate = None
        self.pending_model = None
        self.pending_roi = None
        self.pending_scope = FULL
        self.pending_context = 0
        self.roi = self.roi_start = self.roi_preview = None
        self.scope.set(FULL)
        self._update_roi_label()
        self.free_poly = []
        self.orig_contour = None
        self.orig_contour_full = None
        self.edit_contour = None
        self.base_before_edit = None
        self.vertex_drag = self.selected_vertex = None
        self.vertex_history.clear()
        self.vertex_action.set('Move')
        if self.mode.get() == 'Draw ROI': self.mode.set('Paint fire')
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
        self._refresh_ui()
        if self.render_task is None:
            self.render_task = self.after(33, self._render)

    def _render(self):
        self.render_task = None
        image = self._current_view_image()
        if image is None:
            return
        self.canvas.delete('welcome')
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
        self._refresh_ui()

    def _render_annotations(self):
        self.canvas.delete('guide')
        if self.ir_preview.get():
            return
        box = self.roi_preview or (self.roi if self.scope.get() != FULL else None)
        if box is not None:
            x0, y0, x1, y1 = box
            a, b = self.to_screen((x0, y0)), self.to_screen((x1, y1))
            if self.scope.get() == CROP:
                outer = padded_roi(box, self.image.size, int(self.context_percent.get()))
                if outer != box:
                    self.canvas.create_rectangle(*self.to_screen(outer[:2]), *self.to_screen(outer[2:]),
                                                 outline='#9bc8ed', width=1, dash=(2, 4), tags='guide')
            self.canvas.create_rectangle(*a, *b, outline='#ffbb44', width=2,
                                         dash=(6, 3), tags='guide')
        for x, y, label in self.points:
            if self.scope.get() != FULL and self.roi is not None and not scoped_points([(x,y,label)],self.roi):
                continue
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
        if self.busy or self.image is None or self.ir_preview.get():
            return
        self.canvas.focus_set()
        pos = self.to_image(ev)
        mode = self.mode.get()
        if mode == 'Pan':
            self.pan_last = (ev.x, ev.y)
            return
        if pos is None:
            return
        if mode == 'Draw ROI':
            if self.free_poly or self.orig_contour is not None:
                self.status.set('Finish or cancel the current shape before selecting an ROI.')
                return
            self.roi_start = pos
            self.roi_preview = None
            return
        if mode in ('Paint fire', 'Erase'):
            if self.orig_contour is not None:
                self.status.set('Commit or cancel the boundary edit before painting.')
                return
            self._snapshot()
            self.drag_last = pos
            self._paint(pos)
        elif mode in ('SAM positive','SAM negative'):
            if self.scope.get() != FULL and self.roi is not None and not scoped_points([(*pos,1)],self.roi):
                self.status.set('SAM points must be inside the active ROI. Clear ROI for full-image prompts.')
                return
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
                action='Add' if ev.state & 0x0001 else self.vertex_action.get()
                if action=='Add':
                    self.insert_vertex(ev.x,ev.y)
                else:
                    match=self._nearest_vertex(ev.x,ev.y)
                    if match is not None:
                        self.selected_vertex=match
                        if action=='Remove': self.remove_nearest_vertex()
                        else:
                            self.vertex_drag=match
                            self.vertex_drag_origin=self.edit_contour.copy()
                            self.request_render()
                    else:
                        self.status.set('Click a yellow vertex, or choose Add and click an edge.')

    def left_drag(self, ev):
        if self.busy or self.ir_preview.get():
            return
        mode=self.mode.get()
        if mode == 'Draw ROI' and self.roi_start is not None:
            self.roi_preview = make_roi(self.roi_start, self._roi_pos(ev), self.image.size)
            self._render_annotations()
        elif mode == 'Pan' and self.pan_last is not None:
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
        if self.roi_start is not None:
            if not self.busy and not self.ir_preview.get() and self.mode.get() == 'Draw ROI':
                rect = make_roi(self.roi_start, self._roi_pos(ev), self.image.size)
                if rect is not None:
                    self.roi = rect
                    if self.scope.get() == FULL:
                        self.scope.set(CROP)
                    self._update_roi_label()
                    self._settings_status('ROI selected. Run candidate, or add SAM points inside to refine.')
                else:
                    self.status.set('ROI too small (minimum 8 x 8 image pixels); previous ROI kept.')
            self.roi_start = self.roi_preview = None
            self.request_render()
        self.drag_last=None
        self.pan_last=None
        if self.vertex_drag is not None and self.edit_contour is not None:
            before=getattr(self,'vertex_drag_origin',None)
            if before is not None and before!=self.edit_contour: self._push_vertex_history(before)
        self.vertex_drag=None
        self.vertex_drag_origin=None
        self._refresh_ui()

    def _pan_end(self, ev):
        self.pan_last = None

    def _roi_pos(self, ev):
        x = round((ev.x-self.offset[0])/self.scaling)
        y = round((ev.y-self.offset[1])/self.scaling)
        return (max(0, min(self.image.width-1, x)), max(0, min(self.image.height-1, y)))

    def _invalidate_roi_candidate(self):
        self.pending_candidate = self.pending_model = self.pending_roi = None
        self.pending_scope = FULL
        self.pending_context = 0

    def _settings_status(self, text):
        if self.pending_candidate is not None:
            text += ' | Previous GREEN candidate kept; apply before next inference or saving.'
        self.status.set(text)

    def _update_roi_label(self):
        self.model_box.configure(state='disabled' if self.busy else 'readonly')
        self.scope_box.configure(state='disabled' if self.busy else 'readonly',
                                 values=SCOPES if self.model.get().startswith('SAM2') else (FULL,CROP))
        self.context_box.configure(state='readonly' if self.scope.get() == CROP and not self.busy else 'disabled')
        if self.roi is None:
            self.roi_label.set('No ROI selected')
        else:
            x0,y0,x1,y1 = self.roi
            inactive = ' (inactive)' if self.scope.get() == FULL else ''
            self.roi_label.set(f'{x1-x0} x {y1-y0} px at ({x0}, {y0}){inactive}')

    def _scope_changed(self, ev=None):
        # A running candidate owns its captured scope. Do not change it mid-run.
        if self.busy:
            self.scope.set(self.running_scope)
            return
        self._update_roi_label()
        self._settings_status('Inference area changed. Working mask unchanged.')
        self.request_render()

    def _context_changed(self, ev=None):
        if self.busy:
            self.context_percent.set(str(self.running_context))
            return
        self._update_roi_label()
        self._settings_status('Crop context changed for next inference.')
        self.request_render()

    def _model_changed(self, *_):
        if self.busy:
            return
        if self.scope.get() == BOX and not self.model.get().startswith('SAM2'):
            self.scope.set(CROP)
        self._update_roi_label()
        self._model_options()
        self._settings_status('Model changed for next inference.')
        self.request_render()

    def fit_roi(self):
        if self.image is None or self.roi is None or self.ir_preview.get():
            return
        x0,y0,x1,y1 = self.roi
        cw,ch = max(100,self.canvas.winfo_width()),max(100,self.canvas.winfo_height())
        self.scaling = min(6.0, .85*cw/(x1-x0), .85*ch/(y1-y0))
        self.offset = (cw/2-(x0+x1)/2*self.scaling, ch/2-(y0+y1)/2*self.scaling)
        self.request_render()

    def start_roi(self):
        if self.busy or self.image is None or self.ir_preview.get():
            return
        if self.free_poly or self.orig_contour is not None:
            self.status.set('Finish or cancel the current shape before selecting an ROI.')
            return
        self.mode.set('Draw ROI')
        self.tabs.select(self.segment_tab)
        self.canvas.focus_set()
        self._settings_status('Drag a rectangle around flames. Wheel zoom and right-drag pan available.')

    def clear_roi(self):
        if self.busy or self.ir_preview.get():
            return
        self.roi = self.roi_start = self.roi_preview = None
        self.scope.set(FULL)
        if self.mode.get() == 'Draw ROI':
            self.mode.set('Paint fire')
        self._update_roi_label()
        self._settings_status('ROI cleared. Full-image inference restored.')
        self.request_render()

    def double_click(self, ev):
        if self.mode.get() in ('Polygon add','Polygon erase'):
            self.finish_polygon()

    def _nearest_vertex(self, x, y):
        if self.edit_contour is None:
            return None
        distance, index = min(((math.hypot(x-sx,y-sy),i) for i,p in enumerate(self.edit_contour)
                               for sx,sy in [self.to_screen(p)]),default=(1e9,None))
        return index if distance<=14 else None

    def _nearest_edge(self, x, y):
        if not self.edit_contour: return None
        edges=[]
        for i,a0 in enumerate(self.edit_contour):
            j=(i+1)%len(self.edit_contour); b0=self.edit_contour[j]
            a,b=self.to_screen(a0),self.to_screen(b0)
            vx,vy=b[0]-a[0],b[1]-a[1]; denom=vx*vx+vy*vy
            if not denom: continue
            t=max(0,min(1,((x-a[0])*vx+(y-a[1])*vy)/denom))
            d=math.hypot(x-(a[0]+t*vx),y-(a[1]+t*vy))
            pos=(round(a0[0]+t*(b0[0]-a0[0])),round(a0[1]+t*(b0[1]-a0[1])))
            edges.append((d,i+1,pos,a0,b0))
        if not edges: return None
        d,index,pos,a,b=min(edges,key=lambda edge:edge[0])
        if d>18 or pos in (a,b): return None
        return index,pos

    def _push_vertex_history(self, before=None):
        self.vertex_history.append(list(self.edit_contour if before is None else before))
        if len(self.vertex_history)>50: self.vertex_history.pop(0)

    def _vertex_action_changed(self):
        if self.edit_contour is not None:
            self.canvas.focus_set()
            self._refresh_ui()

    def insert_vertex(self,x,y):
        if self.busy or self.ir_preview.get() or self.edit_contour is None: return False
        result=self._nearest_edge(x,y)
        if result is None:
            self.status.set('Click near the middle of a yellow edge to add a new vertex. Zoom for precision.')
            return False
        index,pos=result
        if pos in self.edit_contour:
            self.status.set('A vertex already exists there.'); return False
        self._push_vertex_history()
        self.edit_contour.insert(index,pos); self.selected_vertex=index
        self.status.set('Vertex added. Choose Move to drag it, or Undo vertex to revert.')
        self.request_render(); return True

    def remove_nearest_vertex(self):
        if self.busy or self.ir_preview.get() or self.edit_contour is None or self.selected_vertex is None: return False
        if len(self.edit_contour)<=3:
            self.status.set('A polygon needs at least three vertices.'); return False
        self._push_vertex_history()
        self.edit_contour.pop(self.selected_vertex); self.vertex_drag=None; self.selected_vertex=None
        self.status.set('Vertex removed. Undo vertex is available until commit.')
        self.request_render(); return True

    def undo_vertex(self):
        if self.busy or self.ir_preview.get() or not self.vertex_history or self.edit_contour is None: return
        self.edit_contour=self.vertex_history.pop(); self.vertex_drag=self.selected_vertex=None
        self.status.set('Last vertex edit undone. Working mask unchanged.')
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
        self.vertex_history.clear()
        self.vertex_action.set('Move')
        self.status.set(f'{len(simplified)} vertices. Drag a point; Shift-click a line to add; Delete selected point; Commit boundary. Only the changed outline area is applied.')
        self.request_render()

    def commit_boundary(self):
        if self.busy or self.ir_preview.get() or self.orig_contour is None or self.edit_contour is None:
            return
        if len(set(self.edit_contour))<3 or abs(cv2.contourArea(np.asarray(self.edit_contour,dtype=np.int32)))<1:
            self.status.set('Invalid boundary: at least three distinct non-collinear vertices required.'); return
        if self.edit_contour==self.orig_contour:
            self.cancel_edit(); self.status.set('No boundary changes; original mask preserved.'); return
        try:
            updated=apply_boundary_delta(self.base_before_edit,self.orig_contour_full,self.orig_contour,self.edit_contour)
        except (ValueError,cv2.error) as exc:
            messagebox.showerror('Boundary edit failed',str(exc)); return
        if updated.tobytes()!=self.mask.tobytes():
            self._snapshot(); self.mask=updated; self.dirty=True; self.source='boundary vertex correction'
            text='Boundary change applied. Save draft to keep it.'
        else: text='No raster change; original mask preserved.'
        self.orig_contour=self.orig_contour_full=self.edit_contour=self.base_before_edit=None
        self.vertex_drag=self.selected_vertex=None; self.vertex_history.clear(); self.vertex_action.set('Move')
        self.status.set(text); self.request_render()

    def finish_polygon(self):
        if self.mask is None or len(self.free_poly)<3 or self.busy or self.ir_preview.get():
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
        self.roi_start = self.roi_preview = None
        self.free_poly=[]
        self.orig_contour=self.orig_contour_full=self.edit_contour=self.base_before_edit=None
        self.vertex_drag=None
        self.selected_vertex=None
        self.vertex_history.clear()
        self.vertex_action.set('Move')
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
        new=min(6.0,max(0.015,old*(1.23 if getattr(ev,'delta',0)>0 or getattr(ev,'num',None)==4 else 1/1.23)))
        ix=(ev.x-self.offset[0])/old
        iy=(ev.y-self.offset[1])/old
        self.scaling=new
        self.offset=(ev.x-ix*new,ev.y-iy*new)
        self.request_render()

    def undo(self):
        if self.busy or self.ir_preview.get(): return
        if self.edit_contour is not None:
            self.undo_vertex(); return
        if self.free_poly:
            self.free_poly.pop(); self.request_render(); return
        if not self.undo_stack: return
        self.cancel_edit()
        self.mask=mask_unpack(self.undo_stack.pop())
        self.dirty=True
        self.source='manual correction (undo)'
        self.request_render()

    def clear_mask(self):
        if self.mask is not None and not self.busy and not self.ir_preview.get():
            if self.free_poly or self.edit_contour is not None or self.roi_start is not None:
                self.status.set('Commit or cancel the current shape before clearing the mask.'); return
            if messagebox.askyesno('Clear mask','Clear current working mask? Undo is available; saved files remain unchanged.'):
                self._snapshot()
                self.mask=Image.new('L',self.mask.size,0)
                self.dirty=True
                self.request_render()

    def clear_prompts(self):
        if self.busy:
            return
        self.points.clear()
        self.request_render()

    def run_candidate(self):
        if self.busy or self.image is None or self.ir_preview.get():
            return
        if self.free_poly or self.orig_contour is not None or self.roi_start is not None:
            messagebox.showinfo('Finish edit', 'Finish or cancel the current shape before inference.')
            return
        variant = self.model.get()
        scope = self.scope.get()
        roi = None if scope == FULL else self.roi
        try:
            if scope != FULL:
                validate_roi(roi, self.image.size)
            if scope == BOX and not variant.startswith('SAM2'):
                raise ValueError('Choose ROI crop for SAM3 text or Colour demo.')
            if variant.startswith('SAM2') and scope == FULL and not any(p[2] for p in self.points):
                raise ValueError('Place at least one positive SAM point for full-image inference.')
            context = int(self.context_percent.get()) if scope == CROP else 0
        except ValueError as exc:
            messagebox.showinfo('Inference area', str(exc))
            return
        if self.pending_candidate is not None:
            choice = messagebox.askyesnocancel('Keep previous prediction?',
                f'Apply the previous green {self.pending_scope} candidate using {self.merge.get()} before running the next inference?\n\n'
                'Yes = apply to working mask, then run.\n'
                'No = discard previous candidate, then run.\n'
                'Cancel = keep candidate and stop.', default='yes')
            if choice is None:
                return
            if choice:
                if not self.apply_candidate():
                    return
            else:
                self.discard_candidate()
        self.busy = True
        self.running_scope = scope
        self.running_context = context
        self._update_roi_label()
        self._invalidate_roi_candidate()
        path = self.image_path
        points = self.points.copy()
        prompt = self.prompt_text.get().strip() or 'flames'
        threshold = float(self.threshold.get())
        self.status.set(f'Running {variant} | {scope}. Current mask unchanged.')
        self.request_render()
        threading.Thread(target=self._candidate_thread,
                         args=(variant,self.image,path,points,prompt,threshold,scope,roi,self.image_generation,context),daemon=True).start()

    def _candidate_thread(self,variant,image,path,points,prompt,threshold,scope,roi,image_generation,context):
        try:
            answer=run_scoped(variant,image,path,points,prompt,threshold,scope,roi,
                              self.sam2,sam3_predict,colour_candidate,image_generation=image_generation,context_percent=context)
            self.running_queue.put(('ok',answer,variant,path,scope,roi,context))
        except Exception:
            self.running_queue.put(('error',traceback.format_exc(),variant,path,scope,roi,context))

    def _check_queue(self):
        while not self.running_queue.empty():
            result,value,variant,path,scope,roi,context=self.running_queue.get_nowait()
            self.busy=False
            self._update_roi_label()
            if path != self.image_path:
                continue
            if result=='error':
                self._refresh_ui()
                self.status.set(f'{variant} failed. Existing mask preserved.')
                messagebox.showerror('Model inference failed',value[-4500:])
            else:
                if value.size != self.mask.size:
                    self._refresh_ui()
                    self.status.set('Candidate discarded because dimensions differ.')
                    messagebox.showerror('Size mismatch','Candidate must have the same dimensions as the RGB image.')
                else:
                    self.pending_candidate=value
                    self.pending_model=variant
                    self.pending_scope=scope
                    self.pending_roi=roi
                    self.pending_context=context
                    self.show_candidate.set(True)
                    self.status.set(f'{variant} | {scope} ready (GREEN, not yet applied). Apply candidate, run another inference or save to keep it.' if value.getbbox() else 'Empty candidate: no foreground detected. Replace/Intersect may clear the inference area.')
                    self.request_render()
        self.after(120,self._check_queue)

    def apply_candidate(self):
        if self.pending_candidate is None or self.mask is None or self.busy or self.ir_preview.get():
            return False
        if self.free_poly or self.orig_contour is not None or self.roi_start is not None:
            messagebox.showinfo('Finish edit', 'Finish or cancel the current shape before applying a candidate.')
            return False
        if self.pending_candidate.getbbox() is None and self.merge.get() in ('Replace','Intersect'):
            if not messagebox.askyesno('Empty candidate', 'No foreground was detected. Clear the mask in the candidate inference area?'):
                return False
        self._snapshot()
        self.mask=merge_scoped(self.mask,self.pending_candidate,self.merge.get(),self.pending_roi,merge_masks)
        self.source=f'{self.pending_model}: {self.merge.get()}'
        if self.pending_roi is not None:
            self.source += f' | {self.pending_scope} XYXY(exclusive)={self.pending_roi}'
            if self.pending_scope == CROP:
                self.source += f' | context={self.pending_context}%'
        self._invalidate_roi_candidate()
        self.dirty=True
        self.status.set('Candidate applied to working mask. Draw another ROI or save; Undo is available.')
        self.request_render()
        return True

    def discard_candidate(self):
        if self.busy:
            return
        self._invalidate_roi_candidate()
        self.status.set('Candidate discarded. Existing mask unchanged.')
        self.request_render()

    def save(self,status):
        if self.busy or self.image_path is None or self.mask is None or self.folder is None:
            return
        if self.ir_preview.get():
            messagebox.showinfo('Switch to RGB','Return to RGB view before saving RGB annotations.')
            return
        if self.orig_contour is not None or self.free_poly or self.roi_start is not None:
            messagebox.showinfo('Finish edit','Commit or cancel the current polygon/boundary/ROI edit first.')
            return
        if self.pending_candidate is not None:
            if not messagebox.askyesno('Apply candidate and save?',
                    f'Include the green {self.pending_scope} candidate in this {status} save using {self.merge.get()}?\n\n'
                    'Yes = apply candidate and save the combined mask.\n'
                    'No = cancel saving and keep the preview.\n'
                    'To save without it, click Discard candidate first.', default='yes'):
                return
            if not self.apply_candidate():
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
            self._refresh_ui()
        except Exception as exc:
            messagebox.showerror('Failed to save annotation',str(exc))


if __name__=='__main__':
    FireAnnotator().mainloop()
