@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
cd /d "%ROOT%" || exit /b 1

echo [1/3] Checking Python...
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

echo [2/3] Installing dependencies from requirements.txt...
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo FAILED: Dependency installation failed.
    exit /b 1
)

echo [3/3] Building .exe...
if not exist "dist" mkdir dist
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name "MeriWatch" --distpath dist ^
  --hidden-import pystray._win32 ^
  --hidden-import PIL._imaging ^
  --hidden-import webview ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import clr ^
  --collect-all curl_cffi ^
  --collect-all webview ^
  app.py
if errorlevel 1 (
    echo FAILED: Build failed.
    exit /b 1
)

echo Done!
if exist "dist\MeriWatch.exe" (
    echo SUCCESS: dist\MeriWatch.exe
    echo.
    echo Share the dist folder contents with others.
) else (
    echo FAILED: Check errors above
)
pause
