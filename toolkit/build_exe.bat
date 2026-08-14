@echo off
setlocal
title Build exe

REM ---------------------------------------------------------------
REM  Build the deliverable .exe.
REM
REM  Two rules for this file (same as mw_update.bat):
REM   1) ASCII only. cmd.exe reads .bat in the system codepage
REM      (CP932 on Japanese Windows), so UTF-8 Japanese turns into
REM      garbage and gets executed as commands.
REM   2) No multi-line ( ) blocks. GitHub raw may serve this file
REM      with LF endings, and cmd.exe mis-parses blocks that span
REM      lines. Every conditional below stays on a single line.
REM
REM  Usage:  build_exe.bat [ProductName] [debug]
REM      ProductName : output name, default "AutoWatch"
REM      debug       : console build so errors stay visible
REM
REM  Output: dist\<ProductName>.exe
REM  This never touches app.py or any other MeriWatch file.
REM ---------------------------------------------------------------

set PRODUCT=%~1
if "%PRODUCT%"=="" set PRODUCT=AutoWatch

REM This file lives in toolkit\, so work one level up.
cd /d "%~dp0.."

echo ============================================
echo   Building: %PRODUCT%
echo ============================================
echo.

echo [1/4] Checking Python ...
set PY=python
where py >nul 2>&1
if not errorlevel 1 set PY=py -3
%PY% --version
if errorlevel 1 echo. & echo [NG] Python not found. Install Python first. & echo. & pause & exit /b 1

echo.
echo [2/4] Installing dependencies ...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r toolkit\requirements.txt pyinstaller
if errorlevel 1 echo. & echo [NG] Could not install dependencies. & echo. & pause & exit /b 1

REM --windowed hides errors. Pass "debug" as the 2nd argument to see them.
set WINMODE=--windowed
if /i "%~2"=="debug" set WINMODE=--console

echo.
echo [3/4] Building .exe  (%WINMODE%)
if not exist dist mkdir dist
%PY% -m PyInstaller --noconfirm --clean --onefile %WINMODE% --name "%PRODUCT%" --distpath dist --hidden-import bs4 --hidden-import webview --hidden-import webview.platforms.winforms --hidden-import clr --collect-all webview --collect-data certifi run_tool.py
if errorlevel 1 echo. & echo [NG] Build failed. Read the messages above. & echo. & pause & exit /b 1

echo.
echo [4/4] Preparing the delivery folder ...
REM config.json must sit next to the exe (see toolkit\watcher.py BASE_DIR).
if exist dist\config.json goto :ready
if exist config.json copy /y config.json dist\config.json >nul
if not exist dist\config.json copy /y toolkit\config.example.json dist\config.json >nul

:ready
echo.
if not exist "dist\%PRODUCT%.exe" echo [NG] The exe was not created. Read the messages above. & echo. & pause & exit /b 1

echo ============================================
echo   [OK] dist\%PRODUCT%.exe
echo ============================================
echo.
echo   Next: double click  toolkit\test_clean_env.bat
echo.
echo   Before shipping to a client:
echo     - run it once on a PC without Python
echo     - edit dist\config.json for that client
echo     - point notifications at the client's Discord or mail
echo     - delete the data folder so your test data is not included
echo.
pause
exit /b 0
