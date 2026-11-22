# Segment Studio

**Local, human-in-the-loop image segmentation editor** with Meta SAM2.1
(click prompts) and optional SAM3 (text prompts). The current annotation preset
is **visible flames in RGB fire photographs**. This is an independent research
prototype, not an official Meta, Hugging Face, or AnyLabeling product.

The application imports existing single-channel binary masks, creates a
separate model-candidate preview, supports manual corrections and exports
reusable binary PNG masks. IR photographs can be paired for **viewing only**;
RGB/IR registration or IR segmentation is **not** implemented.

## Features

- Load a folder of RGB photographs; reopen existing masks automatically.
- SAM2.1 Tiny / Small / Base+ / Large: positive and negative click prompts.
- Optional original SAM3: text prompts such as `flames` (gated checkpoint).
- Candidate preview before applying: Replace, Add, Subtract or Intersect.
- Manual brush and eraser, polygon add/erase, simplified contour-vertex edits,
  undo, pan and zoom, transparent colour overlay and a boundary outline.
- Draft/approved status, mask PNG, overlay JPEG, metadata JSON and CSV manifest.
- Efficient viewport rendering and SAM2 image-embedding reuse on repeated clicks.
- Optional paired IR view with explicit `image_pairs.csv`, not an alignment tool.

**Annotation policy:** foreground = directly visible flames, background = smoke,
vegetation, and completely smoke-occluded flames. Exported masks are 0/255 PNGs.

## Quick start — Windows 10/11

**Prerequisites:** [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or
Anaconda, internet connection, enough free disk space for PyTorch and model
checkpoints, and preferably an NVIDIA CUDA GPU. Setup requires PowerShell and
Windows `curl.exe`. SAM3 requires additional gated-model approval. SAM2 runs
slowly on CPU; the CUDA 12.8 PyTorch wheels target newer NVIDIA GPUs.

Download this repository with **Code → Download ZIP**, extract it, then open a
**Conda-enabled PowerShell** in the extracted `segment-studio` folder.

### Standard installation: editor + SAM2.1

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

The single script creates Conda environment `segment_studio`, installs Git,
PyTorch **2.9.1+cu128**, the official SAM2 Python package, GUI dependencies,
and downloads **SAM2.1 Tiny + Small** checkpoints. It runs basic tests and
writes untracked local settings to `.local/config.json`.

To download all four SAM2.1 sizes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -Models all
```

### Complete installation: editor + SAM2.1 + SAM3

**Before running**, request and receive access to the original checkpoint:

1. Visit [facebook/sam3 on Hugging Face](https://huggingface.co/facebook/sam3).
2. Sign in, accept Meta's license/usage conditions, and request access.
3. Wait until that account is approved. The installer **cannot grant access**.
4. Have a Hugging Face **read** token available from
   [Hugging Face Access Tokens](https://huggingface.co/settings/tokens).
   Never paste the token into a repository file or commit it.

Then run **one command**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -Models all
```

In addition to SAM2.1, this creates `segment_studio_sam3` with PyTorch
**2.10.0+cu128**, a separate clone of official SAM3, and native-Windows fixes
for the missing packages encountered during development (`numpy==1.26.4`,
`setuptools==80.9.0`, `einops==0.8.2`, `triton-windows==3.6.0.post26`,
`pycocotools`, `psutil`). It checks Hugging Face login and, if needed, opens
an interactive terminal login; it then downloads `sam3.pt` and `config.json`.

**Important:** this setup targets the original SAM3 checkpoint rather than
SAM3.1. CUDA/SAM3 inference on Windows and ~8 GB VRAM cannot be guaranteed by
successful imports alone. Native Windows is tested only to the extent reported
in the project tests; upstream SAM2 recommends WSL2 for Windows users.

If SAM3 approval is still pending, prepare its environment without downloading
weights:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -SkipSAM3Download
```

After approval, run the same command **without** `-SkipSAM3Download`.
A setup failure can be retried safely; existing environments, Git clones and
checkpoints are reused, not deleted.

For a **GUI-only** test without downloading CUDA/SAM weights:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -GuiOnly
```

The GUI-only setup supports manual corrections and `Colour demo (not AI)`.

### Launch / check

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\LAUNCH_WINDOWS.ps1
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1
```

You can also run directly after activating the environment:

```powershell
conda activate segment_studio
python .\segment_studio.py
```

### Reuse already installed environments and model weights

If you are migrating from the earlier FireMask workspace **in the same parent
folder**, you can try the new GUI immediately with your existing installation
and checkpoints, before running the installer:

```powershell
conda activate firemask
python .\segment_studio.py
```

The Python backend recognizes the older sibling model folders and the existing
`firemask_sam3` environment. This shortcut assumes those environments and
checkpoint folders are still available and working.

Do **not** delete existing `firemask` or `firemask_sam3` environments or move
existing labels. In the same terminal, you can reuse the existing Conda names:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -GuiEnv firemask -SAM3Env firemask_sam3 -WithSAM3 -Models all
```

If the repository is alongside the older `fire_annotation_poc` and
`FireMask_v2_Workspace`, the application can detect those local checkpoint
folders. For checkpoints stored elsewhere, use parameters:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 `
  -ExistingSam2Models 'D:\my-checkpoints\sam2.1' `
  -ExistingSam3Checkpoint 'D:\my-checkpoints\sam3.pt' `
  -WithSAM3
```

The installer doesn't copy large model files when it can reuse paths; it records
paths in `.local/config.json` (ignored by Git). Environment overrides
`SEGMENT_STUDIO_SAM2_MODELS`, `SEGMENT_STUDIO_SAM3_CKPT`, and
`SEGMENT_STUDIO_SAM3_PYTHON` are supported.

## Annotation workflow

1. Open an RGB folder; previously saved masks are loaded.
2. Select SAM2.1, use **SAM positive** and **SAM negative**, and **Run candidate**.
   For SAM3 text, enter `flames` then run a candidate.
3. View the green preview. The underlying approved mask does **not** change
   until **Apply candidate** is clicked.
4. Choose **Replace** for a new mask, **Add (union)** for missing flames,
   **Subtract** for removing predictions, or **Intersect** for overlapping pixels.
5. Paint or erase, draw a polygon, or use **Edit boundary** to select a connected
   region and adjust yellow vertices. Shift-click adds a vertex; Commit applies.
   Simplified boundary edits can smooth flame tips, so use the brush for detail.
6. **Save draft** or **Approve + save**. The program does not modify your raw RGBs.

For model prompts on a high-resolution image, the first request may be slower
because the image embedding/model must load. Subsequent SAM2.1 requests on the
same image/model reuse the embedding. SAM3 uses a separate process per request
and can be much slower.

### Output layout

For compatibility with already annotated datasets, the default output folder is
still named `firemask_output` (you may rename this in a future migration):

```text
RGB_FOLDER/
  image_001_rgb.jpg
  image_002_rgb.jpg
  input_masks/                        # optional original masks
  image_pairs.csv                     # optional RGB–IR mapping
  firemask_output/
    masks/image_001_rgb.png          # binary 0/255 mask
    overlays/image_001_rgb_overlay.jpg
    metadata/image_001_rgb.json
    annotation_manifest.csv
```

The application prioritizes previously saved masks in `firemask_output/masks/`
over `input_masks/`, `masks/` or `<stem>_mask.png`. Do not put RGB overlays in
mask input folders. Labels must be single-channel and match RGB dimensions.

### Optional paired IR images

Choose **IR folder (optional)** and place `image_pairs.csv` in the RGB directory:

```csv
rgb_file,ir_file
image_001_rgb.jpg,image_001_ir.jpg
```

Only matched images are displayed in IR preview; there is no automatic
registration and no IR annotation propagation. Unpaired RGB images are fine.

## Repository and maintenance

- `segment_studio.py`: GUI and annotation workflow.
- `mask_utils.py`: binary masks, contours, saving, manifests and paired image list.
- `sam_backends.py`: SAM2 local inference and SAM3 subprocess bridge.
- `sam3_worker.py`: isolated SAM3 text inference.
- `SETUP_WINDOWS.ps1`: single installation/reinstallation entry point.
- `LAUNCH_WINDOWS.ps1`, `RUN_CHECKS_WINDOWS.ps1`: run and diagnose.
- `tests/`: fast core tests and optional GUI smoke test.
- `docs/`: troubleshooting and publishing instructions.
- `.local/`, `external/`, `models/`: local/generated only, ignored by Git.

After modifying Python code, you **do not** need to reinstall models; launch the
app again. To publish updates: `git add`, `git commit`, `git push` (see
[GitHub publishing](docs/GITHUB_PUBLISHING.md)). Use a feature branch or pull
request for larger changes; other users can run `git pull` to update their
local checkout without overwriting their untracked data.

## Testing and limits

Fast checks: `python -m unittest discover -s tests -p test_core.py -v`.
Optional desktop smoke test (with Tk display):
`python tests/test_gui_smoke.py`.

Tested here: Python syntax, five core mask tests, GUI smoke test with a synthetic
image. **Not tested in this package build**: clean Windows installation and
checkpoint inference on a fresh computer. Prior SAM2.1 and SAM3 execution
reports came from the developer machine; SAM3 may run out of memory on some
8 GB GPUs. Please report exact errors rather than assuming universal support.

## Acknowledgments / licenses

No license has been selected yet for this editor. Review
[licensing considerations](docs/LICENSING.md) with the relevant code owner(s)
before public release. Upstream
[SAM2](https://github.com/facebookresearch/sam2) and
[SAM3](https://github.com/facebookresearch/sam3) are installed separately at
setup. Their source-code licenses and model-weight terms apply independently.
No Meta code or pretrained checkpoints are bundled in this repository.

If your images or annotations belong to a research laboratory, obtain any
required permission before sharing them publicly. The .gitignore avoids common
file types but is not a substitute for checking `git status` before pushing.