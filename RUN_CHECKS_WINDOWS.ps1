<# Run package checks for the GUI environment; no GPU checkpoint download. #>
[CmdletBinding()]
param([string]$GuiEnv = '', [switch]$WithGUI)
$ErrorActionPreference = 'Stop'
# Keep GUI/checks isolated from optional packages installed in the Windows user site.
$env:PYTHONNOUSERSITE = '1'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Set-Location $PSScriptRoot
if (-not $GuiEnv) {
    $cfgFile = Join-Path $PSScriptRoot '.local\config.json'
    if (Test-Path $cfgFile) { $GuiEnv = (Get-Content $cfgFile -Raw | ConvertFrom-Json).gui_env }
}
if (-not $GuiEnv) { $GuiEnv = 'segment_studio' }
& conda run --no-capture-output -n $GuiEnv python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
if ($WithGUI) {
    foreach ($test in @('test_gui_smoke.py','test_roi_gui.py','test_candidate_workflow_gui.py','test_modern_gui.py')) {
        & conda run --no-capture-output -n $GuiEnv python (Join-Path $PSScriptRoot "tests\$test")
        if ($LASTEXITCODE -ne 0) { throw "GUI test failed: $test" }
    }
}
& conda run --no-capture-output -n $GuiEnv python .\check_setup.py
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic failed.' }
