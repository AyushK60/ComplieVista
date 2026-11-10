@rem CompileVista first-time setup (no admin, no execution-policy change)
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev\Setup.ps1" %*
set RC=%errorlevel%
echo.
pause
endlocal & exit /b %RC%
