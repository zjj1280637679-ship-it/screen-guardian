param(
  [string]$Python = $env:SCREEN_GUARDIAN_PYTHON,
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Script = Join-Path $Root "scripts\screen_guardian_capture.py"
$Dist = if ($OutputDir) { $OutputDir } else { Join-Path $Root "bin" }

if (-not $Python) {
  $Python = "python"
}

& $Python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller is not available. Install it with: $Python -m pip install --user pyinstaller"
}

New-Item -ItemType Directory -Path $Dist -Force | Out-Null

& $Python -m PyInstaller `
  --onefile `
  --clean `
  --name screen-guardian-helper `
  --distpath $Dist `
  --workpath (Join-Path $Root "build\screen-guardian-helper") `
  --specpath (Join-Path $Root "build") `
  --collect-submodules PIL `
  --hidden-import mss `
  $Script

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller build failed."
}

$Exe = Join-Path $Dist "screen-guardian-helper.exe"
if (-not (Test-Path $Exe)) {
  throw "Expected helper was not created: $Exe"
}

Write-Host "Built $Exe"
Write-Host "Use it with:"
Write-Host "`$env:SCREEN_GUARDIAN_HELPER_EXE = `"$Exe`""
