<# Launch Segment Studio from any working directory (Conda must be on PATH). #>
[CmdletBinding()]
param([string]$GuiEnv = '')
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root
if (-not $GuiEnv) {
    $configFile = Join-Path $root '.local\config.json'
    if (Test-Path -LiteralPath $configFile) {
        $cfg = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
        $GuiEnv = $cfg.gui_env
    }
}
if (-not $GuiEnv) { $GuiEnv = 'segment_studio' }
& conda run --no-capture-output -n $GuiEnv python (Join-Path $root 'segment_studio.py')
if ($LASTEXITCODE -ne 0) { throw 'GUI exited with an error; see the traceback above.' }
