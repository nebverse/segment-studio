# Segment Studio

**Local AI-assisted image annotation for visible wildfire flames.**

Segment Studio is a Windows desktop tool for creating, reviewing and correcting full-resolution binary masks from RGB photographs. It combines pretrained SAM models, rectangular region-of-interest (ROI) inference and manual editing in a single workspace.

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![SAM](https://img.shields.io/badge/models-SAM2.1%20%7C%20SAM3-6956B7)

> **New here?** Follow [Installation →](INSTALLATION.md) first. The setup script creates the required Conda environments and installs the software and selected models. You do **not** create environments manually.

## Start here

| I want to… | Go to |
| :--- | :--- |
| Install on a new Windows computer | [Installation guide](INSTALLATION.md) |
| Request SAM3 access and authenticate | [Hugging Face setup](INSTALLATION.md#sam3-access-on-hugging-face) |
| Open images, run models and edit masks | [Annotation guide](ANNOTATION_GUIDE.md) |
| Understand the models and ROI modes | [Model guide](models/README.md) |
| Repair an installation or inference error | [Troubleshooting](TROUBLESHOOTING.md) |
| Update an existing installation | [Updating](INSTALLATION.md#update-an-existing-installation) |

## 1. What can Segment Studio do?

- **Segment:** SAM2.1 click prompts, native SAM2.1 boxes, SAM3 text prompts and a lightweight RGB colour filter.
- **Focus:** draw a rectangular ROI to recover small or missed flames with **any** available model, including SAM3.
- **Refine:** accumulate predictions, paint/erase pixels, draw polygons, move/add/remove vertices and undo edits.
- **Inspect:** zoom, pan, change mask opacity and colour, optionally view paired infrared photographs.
- **Export:** save draft or approved binary PNG masks, visual overlays and annotation metadata.

The current annotation target is flames directly visible in RGB photographs. Smoke, vegetation, reflections, burnt ground and flames fully hidden by smoke are background. IR preview is for inspection only, not image registration or thermal segmentation.

## 2. Supported inference modes

| Model | Full image | Rectangular ROI crop | Native box prompt | Runtime |
| :--- | :---: | :---: | :---: | :--- |
| SAM2.1 Tiny | ✅ | ✅ | ✅ | CPU / NVIDIA CUDA |
| SAM2.1 Small | ✅ | ✅ | ✅ | CPU / NVIDIA CUDA |
| SAM2.1 Base+ | ✅ | ✅ | ✅ | CPU / NVIDIA CUDA |
| SAM2.1 Large | ✅ | ✅ | ✅ | CPU / NVIDIA CUDA |
| SAM3 text (original SAM3) | ✅ | ✅ | — | Separate NVIDIA CUDA worker |
| Colour demo (RGB, not AI) | ✅ | ✅ | — | CPU |

> [!IMPORTANT]
> **SAM3 supports rectangular ROI inference.** Draw a rectangle and enter a text prompt such as `flames`. Segment Studio crops the RGB image, sends it to SAM3 and restores the result to original image coordinates. The separate **SAM2 box prompt** mode is a native SAM2.1 geometric prompt, not a requirement for ROI cropping.

| Mode | How it works |
| :--- | :--- |
| Full image | Process the whole RGB image. SAM2.1 needs at least one positive click; SAM3 uses text. |
| ROI crop | Crop the rectangle with optional surrounding context (default 10% per side). SAM2.1 uses a local box and optional clicks; SAM3 uses text; the RGB filter uses colour. Only the selected rectangle can change. |
| SAM2 box prompt | Encode the full image and use the rectangle as a native SAM2.1 prompt, optionally with clicks. Only the rectangle can change. |

Small is a practical SAM2.1 starting point. Larger models generally demand more resources; their accuracy on wildfire flames is not guaranteed. SAM3 requires gated model access and compatible CUDA hardware. See the [model guide](models/README.md).

## 3. Quick installation

**Requirements:** Windows 10/11 x64, internet, a writable [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda installation, and enough disk space. NVIDIA CUDA is recommended; manual editing, the RGB filter and SAM2.1 CPU mode are available without it.

1. Sign in to GitHub with repository access. Select **Code → Download ZIP**, then extract it to a writable folder (or clone with Git).
2. Open Conda-enabled PowerShell and navigate to the extracted directory.
3. Choose **one** setup command below.
4. Launch after setup completes.

Standard installation (SAM2.1 Tiny + Small):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

Complete installation (all SAM2.1 variants + SAM3; [Hugging Face approval required](INSTALLATION.md#sam3-access-on-hugging-face)):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -Models all
```

Launch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\LAUNCH_WINDOWS.ps1
```

See the [complete installation guide](INSTALLATION.md) for manual-only setup, Tiny-only setup, CPU/CUDA selection, existing checkpoints, authentication, environment creation, tests and updates.

## 4. First annotation

1. Open an RGB image folder.
2. In **Segment**, choose a model. For SAM3 type `flames`; for SAM2.1 add positive clicks on flames and optional negative clicks on background.
3. Select **Full image → Run candidate**. Green is a pending prediction. Inspect it and choose **Add (union) → Apply candidate**.
4. Select **ROI crop → Draw ROI** around a missed flame. Run the same or another model and apply the new candidate. Repeat as needed.
5. In **Edit**, use brush, eraser, polygons or boundary vertices. In **View**, adjust overlays and zoom.
6. **Save draft** while working; **Approve + save** after human review.

> [!TIP]
> Accepted mask pixels are purple by default; green indicates a pending candidate. Switching ROI or model does not discard a pending prediction. Before another inference, choose Yes to apply it, No to discard it, or Cancel to keep it and stop. When saving, Yes includes the pending prediction and No cancels saving. Use Add (union) for cumulative refinement.

See the [illustrated-by-controls annotation workflow and shortcuts](ANNOTATION_GUIDE.md).

## 5. Outputs

New saves are stored **inside the selected RGB folder**, not in the repository:

```text
my_rgb_photos/
  photo_001.jpg
  segment_studio_output/
    masks/photo_001.png
    overlays/photo_001_overlay.jpg
    metadata/photo_001.json
    annotation_manifest.csv
```

Masks are single-channel PNGs at original RGB resolution: 0 = background, 255 = flame. Raw photographs are not modified. Existing saved masks are reopened automatically. Never use coloured overlays as training labels.

## 6. Documentation for maintainers

| Page | Purpose |
| :--- | :--- |
| [Development](DEVELOPMENT.md) | Architecture, test commands and release checklist |
| [Changelog](CHANGELOG.md) | Features and installation fixes |
| [GitHub publishing](GITHUB_PUBLISHING.md) | Private repository maintenance and safe distribution |
| [Licensing](LICENSING.md) | Code ownership and upstream model terms |

**Validation status:** the modern workspace port passed 30 CPU unit tests and four GUI regression scripts in Linux/Xvfb with synthetic images. Model calls in ROI tests are mocked; RGB filter inference is real. The internal prototype was user-tested with SAM3 on Windows. A clean Windows install and live GPU inference in the distributable environments remain to be validated.

Segment Studio is an independent research prototype, not an official Meta or Hugging Face product. It uses pretrained models without training/fine-tuning. No model weights, credentials or research imagery are shipped. No public source license has been selected; consult the rights holders before redistribution. Official [SAM2](https://github.com/facebookresearch/sam2) and [SAM3](https://github.com/facebookresearch/sam3) have separate terms.
