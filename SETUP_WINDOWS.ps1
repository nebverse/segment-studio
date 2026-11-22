<#
Segment Studio: one-command Windows/Conda installation.
  powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3 -Models all

Requirements: Windows 10/11, Miniconda/Anaconda and internet access. No admin
rights normally required. SAM3 requires separate manual Hugging Face approval.
Never uploads any research images or credentials.
#>
[CmdletBinding()]
param(
    [ValidateSet('tiny','tiny-small','all')]
    [string]$Models = 'tiny-small',
    [switch]$WithSAM3,
    [switch]$GuiOnly,
    [switch]$SkipSAM3Download,
    [ValidateSet('auto','cpu','cu126','cu128')]
    [string]$TorchBackend = 'auto',
    [switch]$ReinstallTorch,
    [string]$GuiEnv = 'segment_studio',
    [string]$SAM3Env = 'segment_studio_sam3',
    [string]$ExistingSam2Models = '',
    [string]$ExistingSam3Checkpoint = ''
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$parent = Split-Path -Parent $root
Set-Location $root

function Assert-Success([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed (exit code $LASTEXITCODE). Review the output above." }
}
function Run-InEnv([string]$envName, [string[]]$commandArgs, [string]$step) {
    & conda run --no-capture-output -n $envName @commandArgs
    Assert-Success $step
}
function Install-Torch([string]$envName, [string]$version, [string]$vision, [string]$backend) {
    # A plain pip requirement torch==X considers both +cu126 and +cu128 satisfied.
    # Check the exact local version to prevent silently retaining a wrong wheel.
    $probe = 'import importlib.metadata as m, importlib.util; print(m.version("torch") if importlib.util.find_spec("torch") else "NONE")'
    $existing = & conda run -n $envName python -c $probe
    Assert-Success "Inspect installed PyTorch in $envName"
    $installed = (@($existing | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }) | Select-Object -Last 1)
    $wanted = "$version+$backend"
    if ($installed -eq $wanted) {
        Write-Host "Keeping existing $envName PyTorch $wanted" -ForegroundColor Green
        return
    }
    if ($installed -and $installed -ne 'NONE' -and -not $ReinstallTorch) {
        throw "$envName has PyTorch $installed, but the detected plan wants $wanted. To change it explicitly, rerun with -ReinstallTorch; your other environments are not modified."
    }
    $args = @('python','-m','pip','install')
    if ($installed -and $installed -ne 'NONE') { $args += '--force-reinstall' }
    $args += @("torch==$version", "torchvision==$vision", '--index-url', "https://download.pytorch.org/whl/$backend")
    Run-InEnv $envName $args "Install PyTorch $wanted"
}
function Test-Torch([string]$envName, [string]$backend) {
    if ($backend -eq 'cpu') {
        $code = 'import torch; print("Torch:",torch.__version__,"CUDA:",torch.cuda.is_available()); x=torch.ones((32,32)); assert (x*x).sum().item()==1024'
    } else {
        $cudaVersion = if ($backend -eq 'cu128') { '12.8' } else { '12.6' }
        $code = "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; assert torch.version.cuda == '$cudaVersion', 'Incorrect CUDA build'; x=torch.ones((32,32),device='cuda'); assert (x*x).sum().item()==1024; print('CUDA GPU calculation OK:',torch.cuda.get_device_name(0))"
    }
    Run-InEnv $envName @('python','-c',$code) "Verify actual PyTorch computation in $envName"
}
function Env-Exists([string]$envName) {
    $raw = & conda env list --json
    Assert-Success 'conda env list'
    $data = ($raw | Out-String | ConvertFrom-Json)
    return [bool](@($data.envs | Where-Object { (Split-Path -Leaf $_) -eq $envName }).Count)
}
function Create-Env([string]$envName) {
    if (Env-Exists $envName) {
        Write-Host "Using existing Conda environment: $envName" -ForegroundColor Yellow
    } else {
        & conda create -n $envName python=3.12 pip -y
        Assert-Success "Create Conda environment $envName"
    }
}
function Env-Python([string]$envName) {
    $lines = & conda run -n $envName python -c 'import sys; print(sys.executable)'
    Assert-Success "Locate Python for $envName"
    $path = @($lines | Where-Object { $_.Trim() -match 'python(?:\.exe)?$' } | ForEach-Object { $_.Trim() } | Select-Object -Last 1)
    if (-not $path -or -not (Test-Path -LiteralPath $path[0])) { throw "Could not locate Python for $envName." }
    return $path[0]
}
function Git-Repo([string]$kind, [string]$oldFolder) {
    $newFolder = Join-Path $root "external\$kind"
    if (Test-Path (Join-Path $oldFolder '.git')) { return $oldFolder }
    if (Test-Path $newFolder) {
        if (-not (Test-Path (Join-Path $newFolder '.git'))) {
            throw "Existing directory $newFolder is not a Git repository. Move it manually, then retry."
        }
        return $newFolder
    }
    $repo = "https://github.com/facebookresearch/$kind.git"
    Run-InEnv $GuiEnv @('git','clone',$repo,$newFolder) "Clone Meta $kind"
    return $newFolder
}
function Download-Sam2([string]$name, [string]$folder, [string]$reuse) {
    $destination = Join-Path $folder $name
    if ((Test-Path -LiteralPath $destination) -and (Get-Item -LiteralPath $destination).Length -gt 1000000) {
        Write-Host "Already present: $name"; return
    }
    if ($reuse) {
        $old = Join-Path $reuse $name
        if ((Test-Path -LiteralPath $old) -and (Get-Item -LiteralPath $old).Length -gt 1000000) {
            Write-Host "Reusing existing SAM2 checkpoint: $old"; return
        }
    }
    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { throw 'Windows curl.exe not found.' }
    $url = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/$name"
    $partial = "$destination.part"
    Write-Host "Downloading $name from Meta ..." -ForegroundColor Cyan
    & curl.exe --location --fail --retry 3 --connect-timeout 30 --continue-at - --output $partial $url
    Assert-Success "Download $name"
    if ((Get-Item -LiteralPath $partial).Length -lt 1000000) { throw "Download appears incomplete: $partial" }
    Move-Item -LiteralPath $partial -Destination $destination -Force
    Write-Host "Downloaded: $destination"
}
function Existing-Checkpoint([string[]]$paths) {
    foreach ($p in $paths) { if ($p -and (Test-Path -LiteralPath $p -PathType Leaf) -and
         (Get-Item -LiteralPath $p).Length -gt 2GB) { return $p } }
    return $null
}

Write-Host ''
Write-Host '=== Segment Studio | Windows setup ===' -ForegroundColor Cyan
Write-Host "Project: $root"
Write-Host 'Requires: Windows, Conda, internet; an NVIDIA CUDA GPU is recommended for AI.'
& conda --version
Assert-Success 'Conda availability (install Miniconda and open a Conda-enabled shell)'
if ($GuiOnly -and $WithSAM3) { throw 'Use either -GuiOnly or -WithSAM3, not both.' }
Create-Env $GuiEnv
Run-InEnv $GuiEnv @('python','-c','import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32, "Python 3.12 x64 required"') 'Verify Python 3.12 x64'
$localDir = Join-Path $root '.local'
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
$hardwareFile = Join-Path $localDir 'hardware.json'
$hardwareArgs = @('python',(Join-Path $root 'hardware_probe.py'),'--backend',$TorchBackend,'--output',$hardwareFile)
if ($WithSAM3) { $hardwareArgs += '--with-sam3' }
Run-InEnv $GuiEnv $hardwareArgs 'Inspect Windows hardware and select PyTorch backend'
$hardware = Get-Content -LiteralPath $hardwareFile -Raw | ConvertFrom-Json
$selectedBackend = [string]$hardware.backend
Write-Host "Selected backend: $selectedBackend" -ForegroundColor Cyan
& conda install -n $GuiEnv -c conda-forge git -y
Assert-Success 'Install Git in GUI environment'
Run-InEnv $GuiEnv @('python','-m','pip','install','--upgrade','pip') 'Upgrade GUI pip'
Run-InEnv $GuiEnv @('python','-m','pip','install','-r',(Join-Path $root 'requirements-gui.txt')) 'Install GUI requirements'

$sam2Reuse = $ExistingSam2Models
if (-not $sam2Reuse) {
    $legacy = Join-Path $parent 'fire_annotation_poc\models\sam2.1'
    if (Test-Path -LiteralPath $legacy) { $sam2Reuse = $legacy }
}
$sam2Folder = Join-Path $root 'models\sam2.1'
New-Item -ItemType Directory -Force -Path $sam2Folder | Out-Null

if (-not $GuiOnly) {
    Write-Host 'Installing GUI model backend: official SAM2.1' -ForegroundColor Cyan
    Install-Torch $GuiEnv '2.9.1' '0.24.1' $selectedBackend
    Run-InEnv $GuiEnv @('python','-m','pip','install','--upgrade','wheel','setuptools') 'Install SAM2 build tools'
    $sam2Source = Git-Repo 'sam2' (Join-Path $parent 'sam2_source')
    $env:SAM2_BUILD_CUDA = '0'
    try { Run-InEnv $GuiEnv @('python','-m','pip','install','--no-build-isolation','-e',$sam2Source) 'Install official SAM2' }
    finally { Remove-Item Env:SAM2_BUILD_CUDA -ErrorAction SilentlyContinue }
    Run-InEnv $GuiEnv @('python','-c','from sam2.build_sam import build_sam2; from sam2.sam2_image_predictor import SAM2ImagePredictor; print("SAM2 imports OK")') 'Verify SAM2 import'
    Test-Torch $GuiEnv $selectedBackend
    $files = @('sam2.1_hiera_tiny.pt')
    if ($Models -ne 'tiny') { $files += 'sam2.1_hiera_small.pt' }
    if ($Models -eq 'all') { $files += 'sam2.1_hiera_base_plus.pt','sam2.1_hiera_large.pt' }
    foreach ($file in $files) { Download-Sam2 $file $sam2Folder $sam2Reuse }
    & conda run --no-capture-output -n $GuiEnv git -C $sam2Source rev-parse HEAD
    Assert-Success 'Read SAM2 Git revision'
}

$checkpoint3 = $ExistingSam3Checkpoint
if (-not $checkpoint3) {
    $checkpoint3 = Existing-Checkpoint @(
        (Join-Path $root 'models\sam3\sam3.pt'),
        (Join-Path $parent 'FireMask_v2_Workspace\models\sam3\sam3.pt')
    )
}
$sam3Python = $null
if ($WithSAM3) {
    Write-Host 'Installing optional SAM3 in a separate Conda environment' -ForegroundColor Cyan
    Create-Env $SAM3Env
    Run-InEnv $SAM3Env @('python','-m','pip','install','--upgrade','pip','wheel','setuptools==80.9.0') 'SAM3 build tools'
    Install-Torch $SAM3Env '2.10.0' '0.25.0' $selectedBackend
    Test-Torch $SAM3Env $selectedBackend
    $sam3Source = Git-Repo 'sam3' (Join-Path $parent 'sam3_source')
    Run-InEnv $SAM3Env @('python','-m','pip','install','-e',$sam3Source) 'Install Meta SAM3'
    # SAM3 currently imports these modules even for image inference.  Installing
    # them explicitly prevents missing-module errors found in native Windows setup.
    # Re-pin NumPy and setuptools together at the END to prevent version conflicts.
    Run-InEnv $SAM3Env @('python','-m','pip','install',
        'numpy==1.26.4','setuptools==80.9.0','einops==0.8.2','triton-windows==3.6.0.post26',
        'pycocotools','psutil','huggingface_hub') 'Complete SAM3 Windows dependencies'
    Run-InEnv $SAM3Env @('python','-m','pip','check') 'Check SAM3 dependency consistency'
    Run-InEnv $SAM3Env @('python','-c',
        'import torch,einops,triton,psutil,numpy; from pycocotools import mask; from sam3.model_builder import build_sam3_image_model; from sam3.model.sam3_image_processor import Sam3Processor; print("SAM3 IMPORT TEST PASSED; CUDA:",torch.cuda.is_available())') 'Verify SAM3 imports'
    $sam3Python = Env-Python $SAM3Env
    & conda run --no-capture-output -n $GuiEnv git -C $sam3Source rev-parse HEAD
    Assert-Success 'Read SAM3 Git revision'
    if (-not $checkpoint3 -and -not $SkipSAM3Download) {
        $hfCli = Join-Path (Split-Path -Parent $sam3Python) 'Scripts\hf.exe'
        if (-not (Test-Path -LiteralPath $hfCli)) { throw "Hugging Face CLI not found: $hfCli" }
        Write-Host ''
        Write-Host 'SAM3 checkpoint requires approval: https://huggingface.co/facebook/sam3' -ForegroundColor Yellow
        Write-Host 'Request/check access in a browser before logging in.'
        & $hfCli auth whoami
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Please authenticate interactively; do not paste tokens into any project files.'
            & $hfCli auth login
            Assert-Success 'Hugging Face authentication'
        }
        $dest = Join-Path $root 'models\sam3'
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        Write-Host 'Downloading original SAM3 weights and config (several GB) ...' -ForegroundColor Cyan
        & $hfCli download facebook/sam3 sam3.pt config.json --local-dir $dest
        Assert-Success 'Download gated SAM3 checkpoint (ensure Hugging Face approval)'
        $checkpoint3 = Existing-Checkpoint @((Join-Path $dest 'sam3.pt'))
        if (-not $checkpoint3) { throw "Checkpoint not found or incomplete after download: $dest" }
    }
    if ($checkpoint3) { Write-Host "SAM3 checkpoint: $checkpoint3" }
    else { Write-Warning 'SAM3 environment is ready, but no checkpoint is configured. Rerun -WithSAM3 after Hugging Face approval.' }
} elseif (Env-Exists $SAM3Env) {
    $sam3Python = Env-Python $SAM3Env
}

# Local, untracked config lets the GUI find alternate existing environments and
# checkpoint folders. It contains paths only, NEVER tokens or passwords.
$confdir = Join-Path $root '.local'
New-Item -ItemType Directory -Force -Path $confdir | Out-Null
$effectiveSam2Folder = $sam2Folder
if ($sam2Reuse -and (Test-Path -LiteralPath $sam2Reuse)) {
    $someLocal = @(Get-ChildItem -Path $sam2Folder -Filter '*.pt' -ErrorAction SilentlyContinue).Count
    if ($someLocal -eq 0) { $effectiveSam2Folder = $sam2Reuse }
}
$config = @{
    gui_env = $GuiEnv
    sam3_env = $SAM3Env
    sam2_models = $effectiveSam2Folder
    sam3_python = $sam3Python
    sam3_checkpoint = $checkpoint3
    torch_backend = $selectedBackend
}
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $confdir 'config.json') -Encoding UTF8
Write-Host ''
Write-Host 'Running local tests and diagnostics...' -ForegroundColor Cyan
Run-InEnv $GuiEnv @('python','-m','unittest','discover','-s','tests','-p','test_core.py','-v') 'Mask and annotation tests'
Run-InEnv $GuiEnv @('python','-m','unittest','discover','-s','tests','-p','test_hardware.py','-v') 'Hardware selection tests'
Run-InEnv $GuiEnv @('python',(Join-Path $root 'check_setup.py')) 'Diagnostic check'
Write-Host ''
Write-Host '=== SETUP COMPLETE ===' -ForegroundColor Green
Write-Host "Launch: powershell -NoProfile -ExecutionPolicy Bypass -File .\LAUNCH_WINDOWS.ps1 -GuiEnv $GuiEnv"
Write-Host 'Run model candidates inside the app; initial SAM3 inference may still fail on low-VRAM GPUs.'