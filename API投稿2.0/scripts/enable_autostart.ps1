param([Parameter(Mandatory=$true)][string]$Root)

$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'API_Posting_2_AutoStart.lnk'
$launcher = Join-Path $Root 'auto_start.vbs'

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Launcher not found: $launcher"
}

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
$shortcut.Arguments = '"' + $launcher + '"'
$shortcut.WorkingDirectory = $Root
$shortcut.WindowStyle = 7
$shortcut.Description = 'API Posting 2.0 auto start'
$shortcut.Save()

Write-Host "Auto start enabled: $shortcutPath"
