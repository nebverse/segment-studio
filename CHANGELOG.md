# Changelog

[← Home](README.md)

## Documentation refresh

- Clear capability matrix: **SAM3, all SAM2.1 variants and RGB filter support ROI crop**; native SAM2 box prompting is distinct.
- Shorter README with a dedicated installation guide, automatic environment creation, every setup parameter and Hugging Face authentication.
- Step-by-step annotation, model, troubleshooting and maintainer documentation.
- Documentation-only change; application code, installer, requirements and model versions unchanged.

## Modern workspace and ROI update

- Segment / Edit / View sidebar, progress feedback and persistent save controls.
- Full-image inference, rectangular ROI crop with context for every model, and native SAM2.1 box prompts.
- Full-resolution reconstruction and protection outside captured ROI.
- Preserve pending candidates across model/scope/ROI changes; explicit apply/discard/cancel and apply-and-save confirmation.
- Boundary Move/Add/Remove, vertex undo, local raster difference correction and no-op protection.
- Portable setup retained; improved mixed checkpoint reuse and regression checks. No new GUI dependencies.

## Earlier installation fixes retained

- PowerShell/Conda argument handling and Python user-site isolation.
- Hardware-dependent CUDA/CPU selection and explicit PyTorch replacement option.
- Official SAM2.1 checkpoint hash verification and restricted-network recovery.
- Separate original SAM3 environment and gated checkpoint handling.
