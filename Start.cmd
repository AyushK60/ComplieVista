@rem CompileVista one-click Start - M8-G0 (no admin, no execution-policy change)
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\Start.ps1" %*
if errorlevel 1 (
  echo.
  echo Start failed - read the message above. This window stays open.
  pause
)
endlocal
