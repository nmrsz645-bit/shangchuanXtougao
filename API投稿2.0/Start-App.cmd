@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Migrate-LegacyData.ps1"
if errorlevel 1 (
  echo User data migration failed. Please see legacy-migration-error.txt
  pause
  exit /b 1
)
start "" "%~dp0API_Posting_2.exe"
