@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\pythonw.exe" (
 echo Ambiente nao instalado. Execute scripts\install.bat
 pause
 exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "src\main.py"
