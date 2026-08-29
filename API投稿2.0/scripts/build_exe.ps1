param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$appPath = Join-Path $Root 'app'
$buildDir = Join-Path $Root 'build'
$distDir = Join-Path $Root 'dist'
$name = 'API_Posting_2'

Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $distDir -Recurse -Force -ErrorAction SilentlyContinue

$env:PYTHONPATH = $appPath
python -m PyInstaller `
    --noconfirm `
    --windowed `
    --clean `
    --name $name `
    --paths "$appPath" `
    --distpath "$distDir" `
    --workpath "$buildDir" `
    --collect-submodules desktop_posting `
    "$Root\exe_launcher.py"

$exeDir = Join-Path $distDir $name
foreach ($folder in 'config','data','logs') {
    New-Item -ItemType Directory -Force -Path (Join-Path $exeDir $folder) | Out-Null
}

foreach ($file in 'start_auto.bat','auto_start.vbs','Start-App.cmd','Migrate-LegacyData.ps1','version.json','.publish-exclude.txt') {
    Copy-Item -LiteralPath (Join-Path $Root $file) -Destination $exeDir -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $exeDir 'scripts') | Out-Null
foreach ($file in 'enable_autostart.ps1','disable_autostart.ps1') {
    Copy-Item -LiteralPath (Join-Path $Root "scripts\$file") -Destination (Join-Path $exeDir 'scripts') -Force
}
Get-ChildItem -LiteralPath $Root -Filter '*.bat' | Where-Object { $_.Name -ne 'start_auto.bat' } | Copy-Item -Destination $exeDir -Force
Copy-Item -LiteralPath (Join-Path $Root 'USAGE.txt') -Destination $exeDir -Force

Write-Host "EXE package built: $exeDir"
