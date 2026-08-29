@echo off
set "ROOT=%~dp0"
if exist "%ROOT%API_Posting_2.exe" (
  start "" "%ROOT%API_Posting_2.exe" --auto-start
  exit /b
)
set "PYTHONPATH=%ROOT%app"
pythonw -m desktop_posting.main --base-dir "%ROOT%." --auto-start
if errorlevel 1 python -m desktop_posting.main --base-dir "%ROOT%." --auto-start
