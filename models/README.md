# Local models

This directory is populated by `SETUP_WINDOWS.ps1` after the repository is cloned.
Model weights are intentionally **not** included in Git and are ignored by `.gitignore`.

Expected directories after download:

- `sam2.1/sam2.1_hiera_tiny.pt` (plus other requested sizes)
- `sam3/sam3.pt` and `sam3/config.json` (SAM3 requires Hugging Face access)

The setup can reuse older checkpoint folders without copying them, via a local
`.local/config.json` file or the `-ExistingSam2Models` / `-ExistingSam3Checkpoint`
parameters. The local settings are never committed.

The checkpoints and upstream repositories have their own model and code terms.
