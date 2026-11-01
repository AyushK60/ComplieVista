@rem CompileVista Status
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\Status.ps1" %*
echo.
pause
endlocal
