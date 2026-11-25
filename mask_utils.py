"""Pure mask and contour utilities for Segment Studio (no model imports)."""
from __future__ import annotations

import csv
import json
import zlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}


def is_rgb_image(path: Path) -> bool:
    name = path.stem.lower()
    return (path.is_file() and path.suffix.lower() in IMAGE_EXTS
            and not name.endswith(('_mask', '_overlay', '_preview', '_annotation', '_ir', '_thermal', '_infrared')))


def binary_mask(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as src:
        if src.size != size:
            raise ValueError(f'Mask size {src.size}, RGB image size {size}; resize/align masks explicitly before loading.')
        if src.mode not in ('1', 'L', 'P', 'I', 'I;16'):
            raise ValueError(f'Input mask must be single-channel; received {src.mode}. RGB overlays are not ground truth.')
        values = np.asarray(src.convert('L'))
    unique = np.unique(values)
    if unique.size > 2 and not np.all(np.isin(unique, [0, 1, 255])):
        raise ValueError(f'Mask contains more than two classes/intensities: {unique[:12]}. Map the class IDs before import.')
    return Image.fromarray(np.where(values != 0, 255, 0).astype(np.uint8), 'L')


def mask_pack(mask: Image.Image) -> tuple[tuple[int, int], bytes]:
    return mask.size, zlib.compress(mask.tobytes(), 1)


def mask_unpack(data: tuple[tuple[int, int], bytes]) -> Image.Image:
    size, compressed = data
    return Image.frombytes('L', size, zlib.decompress(compressed))


def merge_masks(base: Image.Image, candidate: Image.Image, mode: str) -> Image.Image:
    a = np.asarray(base) > 0
    b = np.asarray(candidate) > 0
    if mode == 'Replace':
        merged = b
    elif mode == 'Add (union)':
        merged = a | b
    elif mode == 'Subtract':
        merged = a & ~b
    elif mode == 'Intersect':
        merged = a & b
    else:
        raise ValueError(f'Unknown merge mode: {mode}')
    return Image.fromarray(merged.astype(np.uint8) * 255, 'L')


def colour_candidate(rgb: Image.Image) -> Image.Image:
    hsv = np.asarray(rgb.convert('HSV'), dtype=np.uint8)
    hue, saturation, value = [hsv[:, :, idx].astype(np.int16) for idx in range(3)]
    fire = (hue <= 48) & (saturation >= 115) & (value >= 110)
    return Image.fromarray(fire.astype(np.uint8) * 255, 'L')


def detect_component_polygon(mask: Image.Image, point: tuple[int, int], tolerance_px: float,
                             simplify_px: float = 3.0, max_vertices: int = 180, return_full: bool = False):
    """Find nearest OUTER connected contour and simplify for user edit.

    WARNING: editing a whole component may simplify thin serrations or enclosed holes.
    The caller must show the candidate BEFORE committing it.
    """
    array = np.asarray(mask, dtype=np.uint8)
    contours, _ = cv2.findContours(array, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    picked = None
    nearest = float('inf')
    for contour in contours:
        if cv2.contourArea(contour) < 4:
            continue
        dist = cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True)
        rank = 0 if dist >= 0 else -dist
        if rank < nearest:
            nearest = rank
            picked = contour
    if picked is None or nearest > tolerance_px:
        return None
    epsilon = max(1.0, simplify_px)
    polygon = cv2.approxPolyDP(picked, epsilon, True).reshape(-1, 2)
    while len(polygon) > max_vertices:
        epsilon *= 1.2
        polygon = cv2.approxPolyDP(picked, epsilon, True).reshape(-1, 2)
    if len(polygon) < 3:
        return None
    edited = [tuple(map(int, p)) for p in polygon]
    full = [tuple(map(int, p)) for p in picked.reshape(-1, 2)]
    return (edited, full) if return_full else edited


def replace_polygon_component(mask: Image.Image, original: list[tuple[int, int]],
                              edited: list[tuple[int, int]]) -> Image.Image:
    # Do not alter the input image. Rasterize the contour being edited.
    if len(original) < 3 or len(edited) < 3:
        raise ValueError('Polygon requires at least three vertices.')
    # Preserve true original component outline (not the display-simplified polygon).
    # Also preserve any holes already present inside that selected component.
    old_area = Image.new('L', mask.size, 0)
    ImageDraw.Draw(old_area).polygon(original, fill=255)
    new_area = Image.new('L', mask.size, 0)
    ImageDraw.Draw(new_area).polygon(edited, fill=255)
    orig = np.asarray(mask) > 0
    old_inside = np.asarray(old_area) > 0
    new_inside = np.asarray(new_area) > 0
    original_holes = old_inside & ~orig
    combined = (orig & ~old_inside) | (new_inside & ~original_holes)
    return Image.fromarray((combined.astype(np.uint8) * 255), 'L')


def save_png_atomic(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + '.partial.png')
    image.save(temporary)
    temporary.replace(path)


def write_manifest(metadata_folder: Path, path: Path) -> None:
    records = []
    for file in sorted(metadata_folder.glob('*.json')):
        try:
            records.append(json.loads(file.read_text(encoding='utf-8')))
        except (ValueError, OSError):
            continue
    if not records:
        return
    names = sorted(set().union(*(record.keys() for record in records)))
    temp = path.with_suffix('.partial.csv')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        writer.writerows(records)
    temp.replace(path)


def load_image_pairs(csv_path: Path) -> dict[str, str]:
    """Explicit pairing, never automatically assume IR georegistration."""
    if not csv_path.exists():
        return {}
    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        rows = csv.DictReader(f)
        if not {'rgb_file', 'ir_file'}.issubset(rows.fieldnames or []):
            raise ValueError('image_pairs.csv requires rgb_file,ir_file columns.')
        return {row['rgb_file'].strip(): row['ir_file'].strip() for row in rows
                if row.get('rgb_file', '').strip() and row.get('ir_file', '').strip()}


def apply_boundary_delta(mask, full_contour, baseline, edited):
    """Apply only the rasterized change between editable outlines, not wholesale
    simplification. Preserve holes and foreground not connected to the selected
    component. Work on a local bounding crop rather than full-size scratch arrays.
    """
    if baseline == edited:
        return mask.copy()
    coords = list(full_contour) + list(baseline) + list(edited)
    x0=max(0,min(x for x,y in coords)); y0=max(0,min(y for x,y in coords))
    x1=min(mask.width,max(x for x,y in coords)+1); y1=min(mask.height,max(y for x,y in coords)+1)
    if x1<=x0 or y1<=y0: return mask.copy()
    box=(x0,y0,x1,y1); crop=mask.crop(box)
    def raster(poly):
        im=Image.new('L',crop.size,0)
        ImageDraw.Draw(im).polygon([(x-x0,y-y0) for x,y in poly],fill=255)
        return np.asarray(im)>0
    before,after,full=raster(baseline),raster(edited),raster(full_contour)
    orig=np.array(crop)>0
    # Flood only the selected 8-connected component. A separate island within
    # a hole is not removed when the outer polygon is contracted.
    connected=orig.astype(np.uint8)
    sx,sy=full_contour[0]; sx-=x0; sy-=y0
    if not (0<=sx<crop.width and 0<=sy<crop.height and connected[sy,sx]):
        raise ValueError('Original boundary seed is not foreground.')
    cv2.floodFill(connected,None,(sx,sy),2,flags=8)
    selected=connected==2
    removed=before & ~after & selected
    added=after & ~before & ~(full & ~orig)
    changed=(orig & ~removed) | added
    out=mask.copy(); out.paste(Image.fromarray(changed.astype(np.uint8)*255,'L'),box)
    return out
