@echo off
setlocal
rem Build the Windows installer with Inno Setup 6 (requires ISCC in PATH).
rem 1) Run build_windows.bat first to produce dist\InsomniaLauncher.exe
rem 2) Run this script; it compiles InsomniaSetup.iss -> dist\InsomniaLauncherSetup.exe

cd /d "%~dp0.."

where iscc >nul 2>nul
if errorlevel 1 (
    echo error: ISCC (Inno Setup 6 compiler) not found in PATH.
    echo        Install from https://jrsoftware.org/isinfo.php and restart,
    echo        or add "C:\Program Files (x86)\Inno Setup 6" to PATH.
    exit /b 1
)

if not exist "dist\InsomniaLauncher.exe" (
    echo error: dist\InsomniaLauncher.exe missing ^(run build_windows.bat first^)
    exit /b 1
)

echo Compiling installer with Inno Setup...
iscc "packaging\InsomniaSetup.iss"

if errorlevel 1 (
    echo.
    echo Build failed. See messages above.
    exit /b 1
)

echo.
echo Installer built: dist\InsomniaLauncherSetup.exe
echo Share that one file; users run it and the launcher is installed.
endlocal
