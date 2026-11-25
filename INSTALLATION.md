# Installation and updates · Windows

[← Back to Segment Studio](README.md) · [Troubleshooting](TROUBLESHOOTING.md)

## 1. Before you start

| You provide | Setup does automatically |
| :--- | :--- |
| Windows 10/11 x64, internet, free disk space | Creates Python 3.12 Conda environment(s) |
| Miniconda or Anaconda, installed for your user | Installs Git, GUI packages and requested model code |
| Repository access and extracted source | Detects hardware and selects PyTorch CPU/CUDA wheel |
| Compatible NVIDIA driver for CUDA | Checks Python imports, tensor computation and regression tests |
| Optional approved Hugging Face account for SAM3 | Downloads and verifies requested SAM2.1 checkpoints; downloads SAM3 after authentication |

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/download) using its normal Windows installer. A per-user writable installation normally needs no administrator privileges. Open the Conda PowerShell Prompt from Start, or follow [Conda's initialization instructions](https://docs.conda.io/projects/conda/en/latest/user-guide/getting-started.html). Verify:

```powershell
conda --version
```

Do **not** manually create Python environments or install PyTorch first. No separate Python installation or system CUDA Toolkit is normally necessary. The setup does not install GPU drivers. On managed PCs consult IT if an actual Windows administrator/UAC prompt appears.

## 2. Download Segment Studio

### Option A — ZIP (no Git required beforehand)

1. Open [nebverse/segment-studio](https://github.com/nebverse/segment-studio). Sign in with authorized access if private.
2. Select **Code → Download ZIP**.
3. Extract the ZIP fully, for example to `C:\Projects\segment-studio` (actual folder may be named segment-studio-main).
4. In Conda-enabled PowerShell, enter the actual extracted folder:

```powershell
cd "C:\Projects\segment-studio"
Test-Path .\SETUP_WINDOWS.ps1
```

The check must return True. A writable non-synced local folder is preferable for large downloads. GitHub sign-in is separate from Windows admin authentication.

### Option B — Git clone (if Git already available)

```powershell
cd C:\Projects
git clone https://github.com/nebverse/segment-studio.git
cd segment-studio
```

Use an existing writable parent folder. Authenticate to GitHub as prompted.

## 3. Choose one installation profile

All commands below run in the project directory in Conda-enabled PowerShell. Choose the one that fits your needs; do not run all of them in sequence. Profiles can be extended later.

| Profile | Setup arguments | Installed checkpoints |
| :--- | :--- | :--- |
| Manual editing + RGB filter | `-GuiOnly` | None |
| Lightweight SAM2.1 | `-Models tiny` | Tiny |
| Standard (default) | none or `-Models tiny-small` | Tiny, Small |
| All SAM2.1 | `-Models all` | Tiny, Small, Base+, Large |
| SAM2.1 + SAM3 | `-WithSAM3` | Tiny, Small, SAM3 |
| Complete | `-WithSAM3 -Models all` | All five |
| SAM3 access pending | `-WithSAM3 -SkipSAM3Download` | Tiny, Small; SAM3 runtime only if no existing checkpoint |

### Manual / colour filter only

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -GuiOnly
```

### SAM2.1 — choose Tiny, default or all

```powershell
# Tiny only
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -Models tiny
# Default: Tiny + Small
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
# All four
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -Models all
```

The installer retrieves public official Meta SAM2.1 checkpoints through Hugging Face first, with the original Meta server as fallback, and verifies SHA-256. No gated SAM3 approval is needed for SAM2.1.

### SAM3 access on Hugging Face

SAM3 is optional and uses gated weights from the original SAM3 model, not SAM3.1.

1. Create an account or sign in at [Hugging Face](https://huggingface.co/join).
2. Open [facebook/sam3](https://huggingface.co/facebook/sam3). Read the applicable terms, accept/request access and wait for approval if necessary.
3. In [Access Tokens](https://huggingface.co/settings/tokens), create a read token (or fine-grained token authorized to read the gated repository). Use the account that received access.
4. Start setup with one of the SAM3 commands below. If the Hugging Face CLI is not authenticated, setup runs `hf auth login` interactively. Paste the token only into that login prompt when requested; it may not be echoed. You do not need to store it in project files or add it as a Git credential for model download.

> [!CAUTION]
> Never share your token in chat, source code, screenshots or Git. A valid token does not bypass model approval. If a previously authenticated account is wrong, after the SAM3 environment exists use `conda run -n segment_studio_sam3 hf auth whoami` and, if needed, `conda run -n segment_studio_sam3 hf auth login`. Use the correct custom environment name if overridden.

### SAM3 installation commands

```powershell
# SAM3 + Tiny + Small
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3
# Complete: SAM3 + all SAM2.1 variants
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -Models all
# Access still pending: install runtime, skip gated download
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -SkipSAM3Download
```

Run just the chosen command. Once approved, rerun the desired SAM3 profile without SkipSAM3Download. Valid existing checkpoints and environments are reused. The original SAM3 download contains sam3.pt and config.json and is several GB.

> [!IMPORTANT]
> SAM3 in this native-Windows distribution needs the tested NVIDIA CUDA 12.8 configuration. It has no CPU fallback here; even around 8 GiB VRAM may be insufficient. SAM2.1 supports CPU and CUDA. See [hardware troubleshooting](TROUBLESHOOTING.md#hardware-detection-and-cudapytorch-selection).

## 4. Environments and dependencies

| Conda environment | Purpose | Created |
| :--- | :--- | :--- |
| `segment_studio` | Python 3.12, Tkinter/Pillow/OpenCV/NumPy GUI; SAM2.1 and PyTorch 2.9.1 / torchvision 0.24.1 unless GuiOnly | Always |
| `segment_studio_sam3` | Python 3.12, SAM3, PyTorch 2.10.0 / torchvision 0.25.0, Windows-specific dependencies | WithSAM3 |

The environments live in your Conda installation, not the Git directory. Always run the GUI from the first environment. The program automatically starts the separate SAM3 Python worker when needed. Do not combine the environments, install packages with pip --user or upgrade the tested dependency pins without compatibility testing.

Setup isolates Python user-site packages, selects CPU/cu126/cu128 based on hardware, installs official model repositories and records local paths in .local/config.json and the hardware report in .local/hardware.json. It checks real PyTorch computation. Upstream model source revisions are printed; this is not a completely locked environment.

## 5. Launch and verify

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\LAUNCH_WINDOWS.ps1
```

Alternative for the default environment:

```powershell
conda activate segment_studio
python .\segment_studio.py
```

Use the launcher where possible: it respects configured environment names and isolates user-site packages. Do not run the GUI from the SAM3 environment.

```powershell
# Diagnostics and unit tests
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1
# Optional: four desktop GUI regression scripts as well
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1 -WithGUI
```

Then open a real RGB image folder, test the installed model(s), run full-image inference, apply a candidate, run ROI crop, apply and save/reopen. Unit/GUI checks use synthetic or mocked inference and cannot certify live SAM GPU execution.

## 6. Advanced setup options

Most users do not need these. All parameters in SETUP_WINDOWS.ps1:

| Parameter | Values / meaning |
| :--- | :--- |
| -Models | tiny, tiny-small (default), all |
| -GuiOnly | Skip AI install; choose separately from SAM3 |
| -WithSAM3 | Install optional SAM3 environment |
| -SkipSAM3Download | Skip gated download; only useful with WithSAM3 |
| -TorchBackend | auto (default), cpu, cu126, cu128; SAM3 requires compatible cu128 |
| -ReinstallTorch | Explicitly allow replacing incompatible existing PyTorch; not a routine update |
| -GuiEnv | Custom GUI environment name (default segment_studio) |
| -SAM3Env | Custom SAM3 environment name (default segment_studio_sam3) |
| -ExistingSam2Models | Directory containing official SAM2.1 checkpoints |
| -ExistingSam3Checkpoint | Full path to existing original sam3.pt |

Examples (use the ones relevant to your machine):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -TorchBackend cpu
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -Models all -ExistingSam2Models "D:\Models\sam2.1"
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -ExistingSam3Checkpoint "D:\Models\sam3\sam3.pt"
```

SAM2.1 supports older compatible CUDA 12.6, newer CUDA 12.8, or CPU. Hardware detection is conservative; the CUDA version printed by nvidia-smi is driver compatibility, not the installed toolkit version. Check driver/VRAM before forcing a backend. Setup does not silently replace an incompatible PyTorch install. See [Troubleshooting](TROUBLESHOOTING.md).

## 7. Local files after setup

```text
segment-studio/
  segment_studio.py
  SETUP_WINDOWS.ps1
  LAUNCH_WINDOWS.ps1
  models/
    sam2.1/       # verified checkpoints
    sam3/         # optional sam3.pt and config.json
  external/
    sam2/         # upstream code
    sam3/         # optional upstream code
  .local/
    config.json   # generated paths; no tokens
    hardware.json
```

Do not commit downloaded checkpoints, external source clones, local configuration, user data or credentials.

## Update an existing installation

Close the app and back up masks, annotations and .local/config.json. For Git:

```powershell
git status
git switch main
git pull --ff-only origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\LAUNCH_WINDOWS.ps1
```

Resolve local changes before pulling. For ZIP installations, extract the new source separately and copy the changed source/docs into your existing folder, retaining models/, external/, .local/ and Conda environments. Alternatively use a fresh extraction with explicit existing checkpoint paths.

No new GUI packages are required for the modern ROI release or this documentation update. Only rerun setup if adding models or repairing installation. After an installer error, update the source and rerun the same intended profile; valid packages and downloads are reused where possible. Do not delete environments or reinstall PyTorch merely to receive documentation/GUI changes.

[Next: annotate images →](ANNOTATION_GUIDE.md)
