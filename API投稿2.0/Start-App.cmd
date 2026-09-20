@echo off
setlocal
for %%F in ("%~dp0*.exe") do (
  start "" "%%~fF"
  endlocal
  exit /b 0
)
echo The application executable was not found.
endlocal
exit /b 1
