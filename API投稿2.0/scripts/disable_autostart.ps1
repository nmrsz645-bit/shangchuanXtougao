$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'API_Posting_2_AutoStart.lnk'

if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
    Write-Host "Auto start disabled: $shortcutPath"
} else {
    Write-Host "Auto start item not found"
}
