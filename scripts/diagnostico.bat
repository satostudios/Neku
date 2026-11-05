@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
 echo Ambiente nao instalado. Execute scripts\install.bat
 pause
 exit /b 1
)
".venv\Scripts\python.exe" "src\main.py" --diagnostics
echo.
pause
