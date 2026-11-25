# Local models

This directory is populated by `SETUP_WINDOWS.ps1` after the repository is cloned.
Model weights are intentionally **not** included in Git and are ignored by `.gitignore`.

Expected directories after download:

- `sam2.1/sam2.1_hiera_tiny.pt` (plus other requested sizes)
- `sam3/sam3.pt` and `sam3/config.json` (SAM3 requires Hugging Face access)

Users can supply existing checkpoint paths using `-ExistingSam2Models` and
`-ExistingSam3Checkpoint` or the generated, untracked `.local/config.json`.
Model downloads are skipped when the configured local files already exist.

The checkpoints and upstream repositories have their own model and code terms.

## Supported model variants

| GUI model | Official checkpoint | Runtime |
| --- | --- | --- |
| SAM2.1 tiny | `sam2.1_hiera_tiny.pt` | CPU / CUDA |
| SAM2.1 small | `sam2.1_hiera_small.pt` | CPU / CUDA |
| SAM2.1 base+ | `sam2.1_hiera_base_plus.pt` | CPU / CUDA |
| SAM2.1 large | `sam2.1_hiera_large.pt` | CPU / CUDA |
| SAM3 text | `sam3.pt` (original SAM3) | Isolated CUDA worker |
| Colour demo (not AI) | None | CPU |

SAM2.1 official [code](https://github.com/facebookresearch/sam2) and public [model repositories](https://huggingface.co/facebook/sam2.1-hiera-small). Default installation downloads Tiny and Small; `-Models all` downloads all four; SHA-256 checks are in `download_sam2.py`. SAM2.1 supports positive/negative clicks and rectangle prompts. The application chooses CUDA if available and otherwise CPU. Larger variants generally use more resources; evaluate quality on the target images.

Original SAM3 official [code](https://github.com/facebookresearch/sam3) and [gated checkpoint](https://huggingface.co/facebook/sam3). Accept terms/request access using your own Hugging Face account; authenticate interactively. The application uses text prompts and a score threshold, in a separate Python 3.12 environment. Native SAM3 box prompting, video tracking, SAM3.1 and fine-tuning are not implemented.

The working Windows pins are PyTorch 2.9.1 / torchvision 0.24.1 for SAM2.1 and PyTorch 2.10.0 / torchvision 0.25.0 for SAM3. See [PyTorch wheel matrix](https://pytorch.org/get-started/previous-versions/). Keep the isolated SAM3 Windows dependencies from the installer. New UI and ROI features do not require upgrading these packages. Upstream Git source is cloned if absent and its revision is printed; this is not a fully locked reproducible installation. Preserve the working revisions and record them with experiment metadata.
