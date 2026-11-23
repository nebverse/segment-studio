# Installation and inference troubleshooting

All commands below run in Windows PowerShell at the repository root. The
single `SETUP_WINDOWS.ps1` script handles these automatically on a fresh setup;
manual commands are for diagnosing unusual failures.

## Conda isn't recognized

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) and open
**Anaconda Prompt** or a Conda-initialized PowerShell. `conda --version` should
succeed. A Windows user with restricted admin rights can use per-user Conda.

## Restricted Windows accounts: no administrator password needed

Segment Studio's installation is designed for a **user-writable Conda installation**.
The Conda environments are created under the current user's Conda directory, not
in a protected system folder. Cloning a private GitHub repository may show a
**browser authentication** prompt: this signs in to GitHub and is unrelated to
Windows administrator permissions.

Conda may print **"Insufficient permissions to write menu folder. Falling back
to user location."** This is generally a nonfatal warning, not a reason to
enter an administrator password. Some organization-managed computers can still
restrict installation or network access. If Windows presents a real User Account
Control (UAC) dialog requesting an administrator account, do not bypass it:
use a permitted per-user Conda installation or consult IT.

## Fix: PowerShell/Conda Python quoting and roaming user packages

Installer releases before the setup checks were moved into **setup_checks.py**
could fail with:

~~~text
NameError: name 'torch' is not defined
conda run python -c ... m.version(torch) ...
~~~

This was a PowerShell argument quoting issue, **not** a missing GPU. Update the
source code via \`git pull origin main\`, then rerun the same setup command.

If pip mentions unrelated packages such as \`lightly\`, \`rasterio\` or
\`torchgeo\` when installing the fresh GUI environment, Windows may be allowing
packages from \`%APPDATA%\Python\Python312\site-packages\` into the Conda
environment. The installer now sets \`PYTHONNOUSERSITE=1\`, clears inherited
\`PYTHONPATH\`/\`PYTHONHOME\`, and validates the environment before installing
packages. The launcher and check script also disable user-site packages.

**Retry without deleting the existing environment:**

~~~powershell
cd E:\segment-studio
git pull origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -Models all
~~~

Rerunning the installer reuses environments and downloaded files. The first
attempt may have left some packages partially installed, so check the final
output. To verify the GUI Conda environment after installation:

~~~powershell
conda run -n segment_studio python -m pip check
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1
~~~

Do **not** run \`pip install --user\` inside these Conda environments, and do
not reinstall Anaconda as administrator to solve this particular error.

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

## Hardware detection and CUDA/PyTorch selection

The one-command Windows installer runs `hardware_probe.py` first and records
the local result in `.local/hardware.json`. It uses conservative NVIDIA Windows
driver floors CUDA 12.8 >=572.61 and CUDA 12.6 >=561.17; otherwise it falls back
to CPU mode for SAM2. It warns about limited GPU VRAM, RAM, disk and multi-GPU
systems. SAM3 on native Windows uses only the tested CUDA 12.8/Triton 3.6
combination. AMD/Intel GPU acceleration is not configured; CPU fallback
remains available for SAM2.

A mismatch with an existing PyTorch installation is **not automatically
replaced**. Preserve the environment or explicitly use `-ReinstallTorch` after
checking the planned backend. Run `python hardware_probe.py` to see the choice.
The installer checks a real PyTorch CUDA tensor calculation after installation.
The CUDA version printed by `nvidia-smi` is the driver's supported level,
not necessarily a separately installed CUDA Toolkit.

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

The Windows installer includes the SAM3 dependencies needed by its import chain:

```text
numpy==1.26.4
setuptools==80.9.0
einops==0.8.2
triton-windows==3.6.0.post26
pycocotools
psutil
```

These packages remain isolated in `segment_studio_sam3`. An unbounded NumPy upgrade can cause SAM3 dependency conflicts;
setuptools >=82 removed the legacy `pkg_resources` import; and SAM3 also
imports `einops`, `triton` and `pycocotools` modules during startup.

If a dependency is missing in the optional SAM3 environment:

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

New masks are stored in `<RGB_FOLDER>/segment_studio_output/masks/`. The app checks
this folder first and then tries `<RGB_FOLDER>/firemask_output/masks/` (legacy import),
`<RGB_FOLDER>/input_masks/`, `<RGB_FOLDER>/masks/`, and `<RGB_STEM>_mask.png`
beside the photograph. The mask must be a single-channel
0/255 (or 0/1) image with the exact same dimensions. Do not provide coloured
overlay previews as label masks.

## RGB–IR mismatch

IR pairing is for side-by-side visual inspection, not registration or label
transfer. A matching filename or CSV pair does not guarantee optical alignment.
For now, edits/exports are restricted to the RGB coordinate system.
