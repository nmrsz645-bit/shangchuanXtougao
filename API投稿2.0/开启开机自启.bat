@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\enable_autostart.ps1" -Root "%~dp0."
pause
