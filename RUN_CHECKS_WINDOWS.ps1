<# Run package checks for the GUI environment; no GPU checkpoint download. #>
[CmdletBinding()]
param([string]$GuiEnv = '')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $GuiEnv) {
    $cfgFile = Join-Path $PSScriptRoot '.local\config.json'
    if (Test-Path $cfgFile) { $GuiEnv = (Get-Content $cfgFile -Raw | ConvertFrom-Json).gui_env }
}
if (-not $GuiEnv) { $GuiEnv = 'segment_studio' }
& conda run --no-capture-output -n $GuiEnv python -m unittest discover -s tests -p 'test_core.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Mask tests failed.' }
& conda run --no-capture-output -n $GuiEnv python -m unittest discover -s tests -p 'test_hardware.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Hardware tests failed.' }
& conda run --no-capture-output -n $GuiEnv python .\check_setup.py
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic failed.' }
