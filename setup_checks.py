"""Segment Studio installer checks.

All checks are invoked as a Python file instead of `python -c`, because
quoting inline Python through PowerShell and `conda run` is unreliable on Windows.
Only stdlib is used until the relevant packages are installed.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import site
import sys
from pathlib import Path


def verify_python() -> None:
    if sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise RuntimeError("Segment Studio requires 64-bit Python 3.12")
    if site.ENABLE_USER_SITE is not False:
        raise RuntimeError(
            "User site-packages are enabled; installer requires PYTHONNOUSERSITE=1. "
            "Other Python packages could contaminate the Conda environment."
        )
    print("Python environment:", sys.executable)
    print("Python:", sys.version.split()[0], "| user site packages disabled")


def print_torch_version() -> None:
    try:
        print(importlib.metadata.version("torch"))
    except importlib.metadata.PackageNotFoundError:
        print("NONE")


def verify_torch(backend: str) -> None:
    import torch

    if backend == "cpu":
        if torch.version.cuda is not None:
            raise RuntimeError(f"CPU backend requested but PyTorch has CUDA {torch.version.cuda}")
        x = torch.ones((32, 32))
        if (x * x).sum().item() != 1024:
            raise RuntimeError("CPU tensor computation returned an unexpected result")
        print("PyTorch CPU calculation OK:", torch.__version__)
        return

    target = {"cu126": "12.6", "cu128": "12.8"}.get(backend)
    if target is None:
        raise ValueError(f"Unknown backend: {backend}")
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch CUDA is unavailable. Check the NVIDIA driver and GPU.")
    if torch.version.cuda != target:
        raise RuntimeError(
            f"Expected CUDA {target} runtime, but PyTorch has {torch.version.cuda}"
        )
    x = torch.ones((32, 32), device="cuda")
    if (x * x).sum().item() != 1024:
        raise RuntimeError("CUDA tensor computation returned an unexpected result")
    torch.cuda.synchronize()
    print("PyTorch GPU calculation OK:", torch.__version__, torch.cuda.get_device_name(0))


def verify_sam2() -> None:
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    print("SAM2 imports OK")


def verify_sam3() -> None:
    import torch
    import einops
    import triton
    import psutil
    import numpy
    from pycocotools import mask
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor
    print("SAM3 imports OK; CUDA available:", torch.cuda.is_available())


def main() -> int:
    parser = argparse.ArgumentParser(description="Segment Studio setup diagnostics")
    parser.add_argument(
        "check",
        choices=("python-version", "python-path", "torch-version",
                 "torch-compute", "sam2-import", "sam3-import"),
    )
    parser.add_argument("--backend", choices=("cpu", "cu126", "cu128"))
    args = parser.parse_args()
    if args.check == "python-version":
        verify_python()
    elif args.check == "python-path":
        print(Path(sys.executable).resolve())
    elif args.check == "torch-version":
        print_torch_version()
    elif args.check == "torch-compute":
        if not args.backend:
            parser.error("torch-compute requires --backend")
        verify_torch(args.backend)
    elif args.check == "sam2-import":
        verify_sam2()
    elif args.check == "sam3-import":
        verify_sam3()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
