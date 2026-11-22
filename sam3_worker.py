"""Run official Meta SAM3 text inference in a separate Conda environment.

Example:
  python sam3_worker.py --image example.jpg --output output.png \
      --checkpoint models/sam3/sam3.pt --text flames --threshold 0.4

This script runs a single image then exits, releasing GPU memory. No SAM2 imports.
"""
from __future__ import annotations

import argparse
import sys
from contextlib import nullcontext
from pathlib import Path

import numpy as np
from PIL import Image


def infer(image_path: Path, output_path: Path, checkpoint: Path,
          text_prompt: str, score_threshold: float) -> dict:
    import torch
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is not available in the SAM3 environment. Check SEGMENT_STUDIO_SAM3_PYTHON.')
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    with Image.open(image_path) as img:
        rgb = img.convert('RGB').copy()
    # Meta's processor resizes its input to 1008 for inference and returns full-image masks.
    # Do not downscale the saved RGB label; the output mask must match original dimensions.
    print(f'Image={image_path.name} ({rgb.width}x{rgb.height}); prompt={text_prompt!r}',flush=True)
    print('Building SAM3 model; this can require substantial RTX VRAM.',flush=True)
    model = build_sam3_image_model(device='cuda', checkpoint_path=str(checkpoint), load_from_HF=False)
    processor = Sam3Processor(model, device='cuda', confidence_threshold=score_threshold)
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        state=processor.set_image(rgb)
        result=processor.set_text_prompt(state=state, prompt=text_prompt)

    masks=result['masks']
    scores=result['scores']
    if hasattr(scores,'detach'):
        scores=scores.detach().float().cpu().numpy()
    scores=np.asarray(scores).reshape(-1)
    if hasattr(masks,'detach'):
        masks=masks.detach().float().cpu().numpy()
    masks=np.asarray(masks)
    if masks.ndim == 2:
        masks=masks[None,...]
    if masks.ndim == 4 and masks.shape[1] == 1:
        masks=masks[:,0,...]
    if masks.ndim != 3:
        raise RuntimeError(f'Unexpected SAM3 masks shape {masks.shape}')
    combined=np.zeros((rgb.height,rgb.width),dtype=np.uint8)
    accepted=0
    for mask, score in zip(masks,scores):
        if score < score_threshold:
            continue
        accepted += 1
        mask = np.asarray(mask,dtype=np.float32)
        if mask.shape != combined.shape:
            mask=cv2_resize_nearest(mask, (rgb.width,rgb.height))
        combined[mask>0.5]=255
    output_path.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(combined,'L').save(output_path)
    print(f'Candidate stored: {output_path}. Instances={accepted}; mask pixels={int((combined>0).sum())}',flush=True)
    return {'instances':accepted,'positive_pixels':int((combined>0).sum())}


def cv2_resize_nearest(array: np.ndarray, shape: tuple[int,int]) -> np.ndarray:
    # Only use PIL here; cv2 is intentionally not required in the SAM3 environment.
    return np.asarray(Image.fromarray(array).resize(shape,Image.Resampling.NEAREST))


def main():
    ap=argparse.ArgumentParser(description='Official SAM3 text inference in dedicated Python environment')
    ap.add_argument('--image',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--checkpoint',type=Path,required=True)
    ap.add_argument('--text',default='flames')
    ap.add_argument('--threshold',type=float,default=0.4)
    args=ap.parse_args()
    try:
        infer(args.image,args.output,args.checkpoint,args.text,args.threshold)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        msg=str(exc).lower()
        if 'out of memory' in msg:
            print('SAM3 OOM: 8 GB VRAM may be insufficient. Close GPU apps; use SAM2.1 in the GUI or an external larger GPU.',file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':
    main()
