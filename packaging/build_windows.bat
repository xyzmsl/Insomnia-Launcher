@echo off
setlocal
cd /d "%~dp0.."

if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt >nul

python -m PyInstaller ^
  --clean ^
  --onefile ^
  --windowed ^
  --name InsomniaLauncher ^
  --icon ui\assets\icon.png ^
  --add-data "ui\assets\icon.png;ui\assets" ^
  main.py

echo.
echo "Built: %CD%\dist\InsomniaLauncher.exe"
pause