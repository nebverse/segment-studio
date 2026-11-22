# Segment Studio

**Local image annotation and AI-assisted segmentation with SAM2.1 and optional SAM3.**

Segment Studio is a Windows desktop application for manually editing binary masks and previewing AI-generated segmentation candidates. The current annotation target is **flames directly visible in RGB wildfire photographs**. Smoke, vegetation and flames fully hidden by smoke are background.

**Current capabilities:** SAM2.1 positive/negative click prompts; optional SAM3 text prompts; brush and eraser; polygon edits; contour-vertex adjustment; candidate preview/merge; draft and approved masks; optional paired infrared image preview. **RGB–IR registration and IR segmentation are not supported.**

This is an independent research prototype, not an official Meta or Hugging Face product. No research images, pretrained checkpoints or authentication tokens are included.

## Getting started

### 1. Prepare Windows and Conda

You need:

- **Windows 10/11 (64-bit)** and an internet connection.
- **[Miniconda](https://www.anaconda.com/download/success)** or **[Anaconda](https://www.anaconda.com/download)**. Install the Windows distribution using its normal installer. You do not need to install Python separately; Segment Studio creates Python 3.12 Conda environments.
- A **Conda-enabled PowerShell** session. Open the Miniconda/Anaconda PowerShell Prompt from the Start menu, or initialize PowerShell using the [official Conda guide](https://docs.conda.io/projects/conda/en/latest/user-guide/getting-started.html).
- Sufficient storage for packages and model checkpoints; an NVIDIA GPU is recommended for AI inference. The setup checks hardware and supports slower CPU-only SAM2.1 operation.

Check Conda in the terminal:

~~~powershell
conda --version
~~~

You do **not** need Git installed beforehand if you download the repository as a ZIP. Setup installs it into the GUI environment.

### 2. Download the application

**Simplest method:**

1. Open the [Segment Studio GitHub repository](https://github.com/nebverse/segment-studio). Sign in to GitHub if repository access is restricted.
2. Select **Code → Download ZIP**.
3. Extract it to a normal writable folder, e.g. **C:\Projects\segment-studio**. Avoid protected directories; a non-synced local disk is preferable for large downloads.
4. In your Conda-enabled PowerShell, navigate into the actual extracted directory:

~~~powershell
cd "C:\Projects\segment-studio"
~~~

Make sure this folder contains **SETUP_WINDOWS.ps1**, **segment_studio.py**, and **README.md**. Adjust the example path if your extracted ZIP directory has a different name.

**Alternative for Git users:**

~~~powershell
cd C:\Projects
git clone https://github.com/nebverse/segment-studio.git
cd segment-studio
~~~

### 3. Choose your installation

There are **two separate Conda environments**, with different PyTorch dependencies.

| Environment | What it contains | When installed |
| --- | --- | --- |
| **segment_studio** | Python 3.12, application GUI, SAM2.1 and PyTorch **2.9.1** | Always |
| **segment_studio_sam3** | Python 3.12, SAM3, PyTorch **2.10.0**, Triton and supporting libraries | Only with the SAM3 option |

**You always launch the GUI from segment_studio.** When you choose SAM3, the application starts its worker using segment_studio_sam3 automatically. Do not merge these environments.

#### Option A — Standard: GUI + SAM2.1

In the project directory, run **one command**:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
~~~

The installer creates the GUI environment, inspects your hardware, selects a supported PyTorch build, installs the official SAM2.1 package and downloads **SAM2.1 Tiny and Small** checkpoints.

To install **all four** SAM2.1 checkpoints (Tiny, Small, Base+ and Large), run this **instead**:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -Models all
~~~

The commands above are alternatives. Running both is unnecessary.

#### Option B — Complete: GUI + SAM2.1 + SAM3

SAM3's model weights are **gated** on Hugging Face. Before running setup:

1. Create or sign in to [Hugging Face](https://huggingface.co/join).
2. Visit the official [Meta SAM3 checkpoint page](https://huggingface.co/facebook/sam3).
3. Read and accept the terms; request access if necessary and wait for approval.
4. Prepare a **read-access token**, if needed, using [Hugging Face token settings](https://huggingface.co/settings/tokens). Never paste a token into the repository or commit it.

Then run:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -Models all
~~~

This installs **both environments**, the four SAM2.1 checkpoints, and the original SAM3 package. It checks Hugging Face authentication, may prompt for interactive terminal login, and downloads the official **sam3.pt** and **config.json**.

For SAM3 plus only Tiny and Small SAM2.1 checkpoints, omit the all-model flag:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3
~~~

**If SAM3 access is pending**, install its environment now without downloading the gated checkpoint:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -SkipSAM3Download
~~~

After approval, rerun the normal complete command. Existing downloads are reused where possible.

**SAM3 hardware warning:** This native-Windows installation requires the supported NVIDIA GPU/CUDA 12.8 configuration. Import checks do not guarantee successful inference, and GPUs with around 8 GiB VRAM may run out of memory. This application targets original SAM3, not SAM3.1.

#### Option C — GUI without AI models

For manual annotation and the non-AI colour demonstration:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -GuiOnly
~~~

This does **not** install usable SAM2.1 or SAM3 inference.

### 4. Launch the application

After setup finishes, from the **same project directory** run:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\LAUNCH_WINDOWS.ps1
~~~

Or use Python directly with the GUI environment:

~~~powershell
conda activate segment_studio
python .\segment_studio.py
~~~

Do **not** activate segment_studio_sam3 to run the GUI; it is a separate inference environment.

Run diagnostics and local checks using:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_CHECKS_WINDOWS.ps1
~~~

## How to annotate

1. Click **Open RGB folder** and choose a folder with the photographs you want to annotate.
2. Select a SAM2.1 model (start with **SAM2.1 Small**). Choose **SAM positive** to click visible flame pixels and **SAM negative** to identify background/smoke.
3. Click **Run candidate**. The green prediction is only a **preview**: it does not alter your existing mask until applied.
4. Select **Apply as** and click **Apply candidate**:

   | Mode | Effect |
   | --- | --- |
   | **Replace** | Replace the current mask with the prediction |
   | **Add (union)** | Add predicted pixels to the current mask |
   | **Subtract** | Remove predicted pixels from the current mask |
   | **Intersect** | Retain only pixels common to both masks |

5. Correct the result with **Paint fire**, **Erase**, **Polygon add/erase**, or **Edit boundary**. Shift-click near a boundary to insert a new vertex. For narrow flame tips, a zoomed-in brush can preserve more detail than simplified polygon editing.
6. Select **Save draft** while revising or **Approve + save** after reviewing the result.

For SAM3, select **SAM3 text**, enter a prompt such as **flames**, and choose **Run candidate**. SAM3 runs in its separate environment; each request may be slower because the model is loaded by a worker process.

**Mouse/keyboard:** wheel = zoom; right-drag = pan; Ctrl+Z = undo; Ctrl+S = save draft; Esc = cancel an unfinished shape. See [Annotation guide](ANNOTATION_GUIDE.md) for additional controls.

## Where files are saved

Raw RGB images are not modified. Saving annotations creates a **segment_studio_output** directory **inside the selected RGB image folder**, separate from the repository's code:

~~~text
my_rgb_photos/
├── photo_001.jpg
├── photo_002.jpg
├── input_masks/                           # optional existing binary masks
│   └── photo_001.png
├── image_pairs.csv                        # optional RGB–IR pairing
└── segment_studio_output/
    ├── masks/
    │   └── photo_001.png                  # grayscale mask, 0 or 255
    ├── overlays/
    │   └── photo_001_overlay.jpg          # visual preview only
    ├── metadata/
    │   └── photo_001.json
    └── annotation_manifest.csv
~~~

Existing masks are reopened from the saved output folder first. The application also accepts correctly sized single-channel masks under **input_masks**, **masks**, or named using the matching image stem plus **_mask.png**. For backward compatibility only, it can read masks from an older **firemask_output/masks** directory; new saves always use **segment_studio_output**.

**Never use coloured overlay JPEGs as training masks.** Model predictions require manual review.

## Optional infrared preview

Click **IR folder (optional)** to select a folder of matching IR photographs. For explicit matching, place an **image_pairs.csv** file in the RGB folder:

~~~csv
rgb_file,ir_file
photo_001.jpg,photo_001_ir.jpg
~~~

Choose the IR directory in the GUI if it is separate from the RGB directory. The app can also attempt simple filename matching, but **matching filenames do not establish registration**. The IR view is inspection-only; labels and exports remain in RGB coordinates.

See [image_pairs_example.csv](image_pairs_example.csv).

## Automatic hardware detection

The installer checks Windows/Python architecture, primary NVIDIA GPU and driver, compute capability, GPU VRAM, system RAM and free disk space before selecting a PyTorch wheel.

| Detected configuration | Behavior |
| --- | --- |
| Compatible NVIDIA GPU and sufficiently recent driver | CUDA 12.8 PyTorch |
| Supported older NVIDIA GPU/driver | CUDA 12.6 PyTorch |
| No compatible NVIDIA CUDA GPU | CPU-only SAM2.1 |
| SAM3 requested without the tested CUDA 12.8 setup | Installer reports the incompatibility |

Driver and GPU checks use conservative compatibility presets. After installation, a real PyTorch tensor operation verifies the selected backend. **The CUDA version in nvidia-smi reflects driver compatibility, not necessarily a separately installed CUDA Toolkit.** PyTorch wheels include the runtime libraries they need in most cases. The installer does not install GPU drivers.

To run just the hardware check, from a Python-enabled environment:

~~~powershell
python .\hardware_probe.py
~~~

**Advanced options** (usually unnecessary for first-time installation):

~~~powershell
# Force a CPU-only SAM2.1 installation
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -TorchBackend cpu

# Allow an intentional replacement of an incompatible existing PyTorch wheel
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -ReinstallTorch
~~~

Other parameters include **-TorchBackend cu126**, **-TorchBackend cu128**, **-GuiEnv**, **-SAM3Env**, **-ExistingSam2Models**, and **-ExistingSam3Checkpoint**. Mismatching installed PyTorch packages are not silently replaced. Hardware profiles and local model locations are stored under **.local/**, which is excluded from Git.

### Installed directory layout

~~~text
segment-studio/
├── segment_studio.py                # GUI
├── SETUP_WINDOWS.ps1                # installer
├── LAUNCH_WINDOWS.ps1               # launcher
├── models/
│   ├── sam2.1/                      # downloaded SAM2.1 model files
│   └── sam3/                        # optional SAM3 checkpoint
├── external/
│   ├── sam2/                        # official SAM2 source clone
│   └── sam3/                        # optional official SAM3 source clone
└── .local/
    ├── config.json                  # generated model/environment paths
    └── hardware.json                # local hardware-selection report
~~~

**Conda environments are installed within your Conda installation**, not inside this repository folder. The model directories, cloned external code, and generated local config are not committed to Git.

## Further help and project information

| Document or file | Purpose |
| --- | --- |
| [Troubleshooting](TROUBLESHOOTING.md) | Conda, CUDA, dependencies, model downloads and mask issues |
| [Annotation guide](ANNOTATION_GUIDE.md) | Prompting and manual-editing controls |
| [GitHub publishing guide](GITHUB_PUBLISHING.md) | Maintainer workflow for commits and updates |
| [Licensing considerations](LICENSING.md) | Publication and redistribution considerations |
| [models/README.md](models/README.md) | Local model layout |
| [tests/](tests/) | Regression and hardware-selection tests |

**Tested:** Python syntax, core mask tests, hardware-selection tests and a GUI smoke test using a synthetic image. **Not established:** reliable fresh installation on every Windows/GPU combination, or universal SAM3 inference on low-memory hardware.

No open-source license has yet been chosen for Segment Studio. Do not assume this repository is licensed for public redistribution. Consult the relevant rights holder(s) and [Licensing considerations](LICENSING.md) before publishing it. Official [SAM2](https://github.com/facebookresearch/sam2) and [SAM3](https://github.com/facebookresearch/sam3) source/checkpoints are installed separately and have their own terms.
