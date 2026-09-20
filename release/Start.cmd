@echo off
setlocal
set "ROOT=%~dp0"
pushd "%ROOT%" || exit /b 1
if exist "updater\UpdateAgent.exe" "updater\UpdateAgent.exe" --silent --check "updater\updater-config.json"
if exist "app\Start-App.cmd" call "app\Start-App.cmd"
popd
endlocal
