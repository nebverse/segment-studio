# Models and inference

[← Home](../README.md) · [Installation](../INSTALLATION.md) · [Annotation guide](../ANNOTATION_GUIDE.md)

## 1. What is supported?

| Model | Checkpoint | Full image | ROI crop | Native box | Runtime |
| :--- | :--- | :---: | :---: | :---: | :--- |
| SAM2.1 Tiny | sam2.1_hiera_tiny.pt | ✅ | ✅ | ✅ | CPU / CUDA |
| SAM2.1 Small | sam2.1_hiera_small.pt | ✅ | ✅ | ✅ | CPU / CUDA |
| SAM2.1 Base+ | sam2.1_hiera_base_plus.pt | ✅ | ✅ | ✅ | CPU / CUDA |
| SAM2.1 Large | sam2.1_hiera_large.pt | ✅ | ✅ | ✅ | CPU / CUDA |
| SAM3 text | sam3.pt | ✅ | ✅ | — | CUDA worker |
| Colour demo | None | ✅ | ✅ | — | CPU |

### SAM2.1 — promptable segmentation

Tiny is lightest; Small is a practical starting point; Base+ and Large typically require more resources. All accept positive/negative point prompts and native boxes. Full-image inference requires a positive point; ROI crop supplies a local rectangle and accepts optional points. The SAM2 embedding cache distinguishes full images and crops and can reuse the same encoding for prompt refinement.

Default setup downloads Tiny and Small; -Models tiny or -Models all selects alternatives. Official public weights are verified by SHA-256. See [Meta SAM2 code](https://github.com/facebookresearch/sam2) and [official Small checkpoint](https://huggingface.co/facebook/sam2.1-hiera-small).

### SAM3 — text-based segmentation

The original SAM3 identifies instances matching text such as flames and combines masks passing the selected score threshold. It supports **both full image and rectangular ROI crop**. In crop mode, the GUI writes a temporary lossless PNG of the crop and runs the same text-prompt worker, then reconstructs the full-resolution candidate. Native SAM3 geometric prompts, video tracking, SAM3.1 and fine-tuning are not exposed in this application.

SAM3 uses a separate CUDA Python worker per request, so it reloads the model each time. It requires the compatible CUDA 12.8 Windows setup, sufficient VRAM and gated Hugging Face access. See [Meta SAM3 code](https://github.com/facebookresearch/sam3), [official checkpoint](https://huggingface.co/facebook/sam3) and [authentication instructions](../INSTALLATION.md#sam3-access-on-hugging-face).

### RGB colour demo

A non-learned RGB heuristic, useful for lightweight segmentation/manual workflows. No model, GPU or text/click prompt required. It can produce false positives on non-flame objects.

## 2. ROI vs native box

ROI crop changes the image passed to the model; context (default 10% on each side, 0–50% configurable) expands what the model sees. Predictions are clipped to the selected rectangle and restored in RGB coordinates. Native SAM2 box retains full-image encoding and uses the rectangle as a model prompt. Both protect mask pixels outside the original ROI. Cropping can improve small-flame detail, but fixed model input resolutions mean speed/memory savings are not guaranteed.

## 3. Local checkpoint layout

Setup creates these paths when requested:

```text
models/
  sam2.1/
    sam2.1_hiera_tiny.pt
    sam2.1_hiera_small.pt
    sam2.1_hiera_base_plus.pt
    sam2.1_hiera_large.pt
  sam3/
    sam3.pt
    config.json
```

Only requested files are downloaded. Reuse existing official checkpoints with -ExistingSam2Models (folder) and -ExistingSam3Checkpoint (file). Setup preserves a valid configured external SAM2 path and fills missing requested sizes locally. The backend searches SEGMENT_STUDIO_SAM2_MODELS, local models/sam2.1 and the configured external directory. SAM3 can use SEGMENT_STUDIO_SAM3_CKPT and SEGMENT_STUDIO_SAM3_PYTHON overrides. Prefer generated .local/config.json to manual changes.

Weights and local settings are not committed. Use approved official downloads; separate upstream licenses apply.

## 4. Runtime compatibility

Python 3.12; GUI/SAM2.1 PyTorch 2.9.1 and torchvision 0.24.1; SAM3 PyTorch 2.10.0 and torchvision 0.25.0. SAM3 also has specific Windows dependency pins in SETUP_WINDOWS.ps1. See the [PyTorch wheel matrix](https://pytorch.org/get-started/previous-versions/). Keep the two environments isolated. No new model or GUI packages are required by ROI/boundary features.

These are pretrained general-purpose models, not wildfire-trained classifiers. Compare accuracy and runtime on representative labelled fire imagery, recording model revision, threshold, ROI/context, hardware and software versions. No measured ranking or guaranteed quality is claimed.
