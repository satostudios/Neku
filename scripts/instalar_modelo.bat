@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_modelo.ps1" %*
echo.
pause
