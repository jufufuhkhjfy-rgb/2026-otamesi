@echo off
setlocal
cd /d "%~dp0"

REM ---------------------------------------------------------------
REM  MeriWatch updater - double click to update and restart.
REM  Keep this file ASCII-only with CRLF line endings. cmd.exe reads
REM  .bat in the system codepage (CP932 on Japanese Windows), so
REM  UTF-8 Japanese text turns into garbage and gets run as commands.
REM ---------------------------------------------------------------

title MeriWatch Updater
echo ================================
echo   MeriWatch Updater
echo ================================
echo.

if not exist run.bat (
  echo [NG] Put this file in the MeriWatch folder and run it there.
  echo      Current folder: %CD%
  echo.
  pause
  exit /b 1
)

REM Stop only the process holding port 5001, which is MeriWatch itself.
REM Killing pythonw.exe by name would take down other scripts too.
echo Stopping MeriWatch if it is running ...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5001" ^| findstr LISTENING') do (
  taskkill /f /pid %%P >nul 2>&1
)

REM Browser downloads get cached and silently return an old file,
REM so fetch with no-cache headers instead.
set URL=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/app.py

echo Downloading latest app.py ...
curl -L -f -s -S -H "Cache-Control: no-cache" -H "Pragma: no-cache" -o app.py.new "%URL%"
if errorlevel 1 (
  echo.
  echo [NG] Download failed. Check your internet connection.
  del /q app.py.new 2>nul
  echo.
  pause
  exit /b 1
)

REM A truncated download must never replace a working file.
set SIZE=0
for %%A in (app.py.new) do set SIZE=%%~zA
if %SIZE% LSS 50000 (
  echo.
  echo [NG] Downloaded file is too small ^(%SIZE% bytes^). Aborted.
  del /q app.py.new 2>nul
  echo.
  pause
  exit /b 1
)

REM Keep the previous file. settings.json and purchases.json are untouched.
if exist app.py copy /y app.py app.py.bak >nul
move /y app.py.new app.py >nul

echo.
echo [OK] Updated: %SIZE% bytes  ^(previous version kept as app.py.bak^)
echo.
echo Starting MeriWatch ...
start "" run.bat
timeout /t 3 >nul
