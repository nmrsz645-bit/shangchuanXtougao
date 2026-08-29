@echo off
set "ROOT=%~dp0"
if exist "%ROOT%API_Posting_2.exe" (
  start "" "%ROOT%API_Posting_2.exe"
  exit /b
)
set "PYTHONPATH=%ROOT%app"
python -m desktop_posting.main --base-dir "%ROOT%."
