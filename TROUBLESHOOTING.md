# Installation and inference troubleshooting

All commands below run in Windows PowerShell at the repository root. The
single `SETUP_WINDOWS.ps1` script handles these automatically on a fresh setup;
manual commands are for diagnosing unusual failures.

## Conda isn't recognized

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) and open
**Anaconda Prompt** or a Conda-initialized PowerShell. `conda --version` should
succeed. A Windows user with restricted admin rights can use per-user Conda.

## Quick environment diagnosis

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1
conda activate segment_studio
python -m pip check
python -c "import torch; print(torch.__version__,torch.version.cuda,torch.cuda.is_available())"
```

The standard CUDA build expects a compatible NVIDIA driver. The CUDA version
shown by `nvidia-smi` is the driver's maximum runtime compatibility, not proof
of a matching system CUDA toolkit. Full SAM performance depends on GPU/VRAM.

## SAM2 checkpoint missing

The default setup downloads `models/sam2.1/sam2.1_hiera_tiny.pt` and Small.
Rerun the installer to repair missing downloads. If your checkpoints already
exist elsewhere, reuse the folder with `-ExistingSam2Models` (do not copy or
rename checkpoints randomly). The downloader keeps partial files on network
failure so a repeat can resume.

## SAM2 install fails on Windows

Meta recommends Ubuntu under Windows Subsystem for Linux (WSL2). This installer
sets `SAM2_BUILD_CUDA=0` to skip an optional Windows CUDA extension while still
using PyTorch CUDA inference. If your particular driver/PyTorch/setup cannot
load the models, compare with upstream [SAM2 installation](https://github.com/facebookresearch/sam2/blob/main/INSTALL.md).

## SAM3 access denied (401/403)

SAM3's model weights are gated: request/accept access at
<https://huggingface.co/facebook/sam3>, authenticate with an approved account,
and rerun the installer. The token is stored by Hugging Face outside this Git
repository. **Do not** put tokens in PowerShell scripts, config files or Git.

## SAM3 missing-module errors on Windows

The Windows installer includes the missing dependencies discovered while
bringing up the original SAM3 repository:

```text
numpy==1.26.4
setuptools==80.9.0
einops==0.8.2
triton-windows==3.6.0.post26
pycocotools
psutil
```

These packages remain isolated in `segment_studio_sam3`. In the earlier
prototype, an unbounded NumPy upgrade caused SAM3 dependency conflicts;
setuptools >=82 removed the legacy `pkg_resources` import; and SAM3 also
imported `einops`, `triton` and `pycocotools` modules during startup.

If the packages are missing in your already-existing SAM3 environment:

```powershell
conda activate segment_studio_sam3
python -m pip install "numpy==1.26.4" "setuptools==80.9.0" "einops==0.8.2" "triton-windows==3.6.0.post26" pycocotools psutil
python -m pip check
python -c "from sam3.model_builder import build_sam3_image_model; from sam3.model.sam3_image_processor import Sam3Processor; print('SAM3 IMPORT OK')"
```

`pkg_resources is deprecated` / `timm.models.layers is deprecated` are warnings,
not import failures. Imports alone do not validate SAM3 CUDA inference.

## SAM3 worker out of memory

SAM3 is a large model; 8 GB GPUs may fail even when imports and CUDA tests pass.
Close other GPU applications, use a single RGB image, or use SAM2.1 as the
baseline. The SAM3 worker runs in a separate process, which frees GPU memory
on exit; this also causes each SAM3 request to reload weights and be slower.
Use a larger VRAM GPU/WSL2 Linux machine for high-throughput evaluation.

## Masks are not loading after restart

Stored masks are in `<RGB_FOLDER>/firemask_output/masks/`. The app checks this
folder first and then tries `<RGB_FOLDER>/input_masks/`, `<RGB_FOLDER>/masks/`,
and `<RGB_STEM>_mask.png` beside the photograph. The mask must be a single-channel
0/255 (or 0/1) image with the exact same dimensions. Do not provide coloured
overlay previews as label masks.

## RGB–IR mismatch

IR pairing is for side-by-side visual inspection, not registration or label
transfer. A matching filename or CSV pair does not guarantee optical alignment.
For now, edits/exports are restricted to the RGB coordinate system.
