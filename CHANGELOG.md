# Changelog

## Modern workspace and ROI update

- Segment / Edit / View sidebar; grouped controls, progress feedback, persistent save controls.
- Full image, cropped rectangular ROI with context and native SAM2.1 box prompting.
- Full-resolution ROI reconstruction, captured inference area and outside-ROI mask protection.
- Keep pending predictions across model/scope/ROI changes; explicit apply/discard/cancel before new inference and apply-and-save confirmation.
- Boundary Move/Add/Remove, vertex undo, local raster boundary correction and no-op protection.
- Keep original Segment Studio portable setup, model download verification and separate environments; improve checkpoint reuse and checks.
- Update documentation and add ROI, candidate workflow and boundary regressions. No new dependencies required.

## Previous installation fixes retained

- Windows PowerShell/Conda argument handling and isolated user site-packages.
- Hardware-dependent CUDA/CPU selection, explicit PyTorch replacement option.
- Official SAM2.1 downloads with hash verification and restricted-network recovery.
- Separate optional original SAM3 runtime and gated checkpoint handling.
