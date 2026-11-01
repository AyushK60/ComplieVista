@rem CompileVista one-click Stop - stops ONLY launcher-owned processes
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\Stop.ps1" %*
if errorlevel 1 (
  echo.
  echo Stop failed - read the message above.
  pause
) else (
  echo (You can close this window.)
)
endlocal
