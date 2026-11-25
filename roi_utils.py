"""ROI inference helpers; coordinates are original-image pixels, right/bottom exclusive."""
from __future__ import annotations
import math
import tempfile
from pathlib import Path
from PIL import Image

FULL = 'Full image'
CROP = 'ROI crop'
BOX = 'SAM2 box prompt'
SCOPES = (FULL, CROP, BOX)
MIN_ROI = 8


def make_roi(a, b, size):
    """Inclusive mouse pixels -> clipped, half-open Pillow crop rectangle."""
    w, h = size
    x0, x1 = sorted((int(a[0]), int(b[0])))
    y0, y1 = sorted((int(a[1]), int(b[1])))
    x0, x1 = max(0, x0), min(w, x1 + 1)
    y0, y1 = max(0, y0), min(h, y1 + 1)
    if x1-x0 < MIN_ROI or y1-y0 < MIN_ROI:
        return None
    return (x0, y0, x1, y1)


def validate_roi(roi, size):
    if roi is None:
        raise ValueError('Draw an ROI first using the Draw ROI tool.')
    x0, y0, x1, y1 = roi
    if not (0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1]
            and x1-x0 >= MIN_ROI and y1-y0 >= MIN_ROI):
        raise ValueError('Invalid or too small ROI.')
    return roi


def scoped_points(points, roi, translate=False):
    if roi is None:
        return list(points)
    x0, y0, x1, y1 = roi
    return [(x-x0 if translate else x, y-y0 if translate else y, label)
            for x, y, label in points if x0 <= x < x1 and y0 <= y < y1]


def padded_roi(roi, size, percent):
    """Expand inference crop by a percentage of ROI width/height on each side."""
    if not 0 <= percent <= 50:
        raise ValueError('ROI context must be 0–50%.')
    x0, y0, x1, y1 = roi
    dx, dy = math.ceil((x1-x0)*percent/100), math.ceil((y1-y0)*percent/100)
    return (max(0,x0-dx), max(0,y0-dy), min(size[0],x1+dx), min(size[1],y1+dy))


def sam_box(roi):
    # SAM2 XYXY uses image coordinates. Last valid pixel is right/bottom - 1.
    x0, y0, x1, y1 = roi
    return (x0, y0, x1-1, y1-1)


def run_scoped(variant, image, path, points, prompt, threshold, scope, roi,
               sam2, sam3_predict, colour_candidate, image_generation=None, context_percent=0):
    """Run existing model APIs without changing weights, env paths or source images."""
    if scope not in SCOPES:
        raise ValueError(f'Unknown inference scope: {scope}')
    roi = None if scope == FULL else validate_roi(roi, image.size)
    is_sam2 = variant.startswith('SAM2')
    if scope == BOX and not is_sam2:
        raise ValueError('SAM2 box prompt is only for SAM2.1; choose ROI crop for other models.')
    cropped = scope == CROP
    crop = padded_roi(roi, image.size, context_percent) if cropped else None
    model_image = image.crop(crop) if cropped else image
    local_points = scoped_points(points, roi)
    if cropped:
        local_points = [(x-crop[0],y-crop[1],label) for x,y,label in local_points]
    if is_sam2 and scope == FULL and not any(p[2] for p in local_points):
        raise ValueError('Place at least one positive SAM point for full-image inference.')
    # Cache distinguishes original image instance and crop; points/box are decoder prompts.
    key = str((str(path.resolve()), image_generation if image_generation is not None else id(image), crop))
    if variant == 'Colour demo (not AI)':
        answer = colour_candidate(model_image)
    elif is_sam2:
        if scope == BOX:
            answer = sam2.predict(variant, model_image, local_points, key, box=sam_box(roi))
        elif cropped:
            # Use the ROI as a box, optionally refined with positive/negative points.
            x0,y0,x1,y1 = roi
            local_box = (x0-crop[0],y0-crop[1],x1-crop[0],y1-crop[1])
            answer = sam2.predict(variant, model_image, local_points, key, box=sam_box(local_box))
        else:
            answer = sam2.predict(variant, model_image, local_points, key)
    elif variant == 'SAM3 text':
        sam2.clear()
        if cropped:
            # Lossless temporary crop; worker and its separate conda env stay untouched.
            with tempfile.TemporaryDirectory(prefix='segment_studio_roi_') as tmp:
                crop_path = Path(tmp) / 'roi.png'
                model_image.save(crop_path)
                answer = sam3_predict(crop_path, prompt, threshold)
        else:
            answer = sam3_predict(path, prompt, threshold)
    else:
        raise ValueError(f'Unknown model choice: {variant}')
    if answer.size != model_image.size:
        raise ValueError(f'Model mask size {answer.size} differs from input {model_image.size}.')
    answer = answer.convert('L').point(lambda p: 255 if p else 0)
    if roi is None:
        return answer
    result = Image.new('L', image.size, 0)
    if cropped:
        x0,y0,x1,y1 = roi
        answer = answer.crop((x0-crop[0],y0-crop[1],x1-crop[0],y1-crop[1]))
    else:
        answer = answer.crop(roi)
    result.paste(answer, roi[:2])
    return result


def merge_scoped(base, candidate, mode, roi, merge_masks):
    """Apply all four operations only inside the candidate's original ROI."""
    if base.size != candidate.size:
        raise ValueError('Candidate dimensions differ from current mask.')
    if roi is None:
        return merge_masks(base, candidate, mode)
    validate_roi(roi, base.size)
    result = base.copy()
    result.paste(merge_masks(base.crop(roi), candidate.crop(roi), mode), roi[:2])
    return result
