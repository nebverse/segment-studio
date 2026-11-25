# Development and release checks

[← Home](README.md) · [Installation](INSTALLATION.md) · [Repository maintenance](GITHUB_PUBLISHING.md)

Segment Studio is the distributable application, not the internal FireMask development workspace. Use portable repository names, relative paths, `.local/config.json`, `segment_studio` / `segment_studio_sam3` environments and `segment_studio_output` for new saves. Read legacy `firemask_output` masks without modifying them. Do not package model weights, lab datasets, credentials or internal environment names.

| File | Responsibility |
| --- | --- |
| `segment_studio.py` | Tkinter interface, image state, candidate transactions, editing and saves |
| `roi_utils.py` | Original-coordinate rectangle geometry, context padding, cropped inference, reconstruction and scoped merge |
| `mask_utils.py` | Binary masks, connected contours, raster boundary delta, overlay and manifest utilities |
| `sam_backends.py` | Portable model discovery, SAM2 embedding cache and SAM3 subprocess |
| `sam3_worker.py` | Single original SAM3 image/text inference in separate environment |
| `SETUP_WINDOWS.ps1` | Conda setup, hardware-aware PyTorch, official models, checks and local config |
| `hardware_probe.py`, `setup_checks.py`, `check_setup.py` | Hardware selection, runtime and setup diagnostics |
| `download_sam2.py` | Official checkpoint downloads and SHA-256 checks |
| `LAUNCH_WINDOWS.ps1`, `RUN_CHECKS_WINDOWS.ps1` | Launch and diagnostics |

## Inference architecture

- Full image: pass RGB to the selected model.
- ROI crop: pad the selected rectangle, run SAM2.1 with a local box and optional clicks, SAM3 with text on a temporary lossless PNG, or the RGB heuristic; clip and place the answer at original RGB coordinates.
- Native SAM2 box: retain full-image embedding and use a geometric box prompt. Not exposed for SAM3.
- Candidate state captures the original inference scope and ROI, so changing UI settings cannot change where a pending candidate is merged. Keep temporary predictions separate from the accepted mask.

## Tests

From the root in the distributable GUI environment on a test computer (or run the Python unit tests in the existing internal FireMask environment with compatible dependencies; this does not validate the distributable installer):

```powershell
python -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1 -WithGUI
```

Unit discovery is headless and uses mocked model calls for ROI logic. The four GUI scripts use synthetic imagery and actual RGB-filter inference, not model weights. GUI scripts run directly and are guarded against execution on unittest import. On Linux with a display or Xvfb, run each `tests/test_gui_smoke.py`, `tests/test_roi_gui.py`, `tests/test_candidate_workflow_gui.py`, `tests/test_modern_gui.py` with Python (prefix with `xvfb-run -a` when needed). Linux is a test environment, not a supported one-command install target.

Before merging a release, validate on Windows: clean GUI-only installation, default SAM2.1 install and CPU/CUDA fallback, complete SAM3 install with approved checkpoint, launch from a path with spaces, reused partial checkpoint sets, full image → ROI → another model → save/reopen, empty prediction confirmation, contour vertex edits, legacy mask loading, high-DPI controls and unchanged raw images. Run real inference for each installed model; mocked calls do not validate GPU, model quality or downloads. Record package versions (`python -m pip freeze` privately), upstream model commit IDs, GPU/driver, thresholds and ROI context for scientific comparisons. Do not commit machine-specific output.

## Release workflow

Start from current `main`; branch, port only tested changes, run checks, inspect `git diff` and staged file names, open a PR, review, then merge. Keep existing setup fixes and dependency pins unless a separately tested compatibility change is required. Existing installations normally need only source updates. Check licensing and institutional approval before public redistribution.
