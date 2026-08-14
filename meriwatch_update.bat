@echo off
setlocal
cd /d "%~dp0"

REM ---------------------------------------------------------------
REM  MeriWatch updater
REM  Keep this file ASCII-only. cmd.exe reads .bat in the system
REM  codepage (CP932 on Japanese Windows), so UTF-8 Japanese text
REM  turns into garbage and gets executed as a command.
REM ---------------------------------------------------------------

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

REM Browser caching served stale copies, so fetch with no-cache headers.
set URL=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/app.py

echo Downloading latest app.py ...
curl -L -f -H "Cache-Control: no-cache" -H "Pragma: no-cache" -o app.py.new "%URL%"
if errorlevel 1 (
  echo.
  echo [NG] Download failed. Check your internet connection.
  del /q app.py.new 2>nul
  echo.
  pause
  exit /b 1
)

REM Sanity check: a truncated download must not replace a working file.
for %%A in (app.py.new) do set SIZE=%%~zA
if %SIZE% LSS 50000 (
  echo.
  echo [NG] Downloaded file is too small ^(%SIZE% bytes^). Aborted.
  del /q app.py.new 2>nul
  echo.
  pause
  exit /b 1
)

REM Keep the previous file. settings.json / purchases.json are untouched.
if exist app.py copy /y app.py app.py.bak >nul
move /y app.py.new app.py >nul

echo.
echo [OK] Updated: %SIZE% bytes
echo      Previous version saved as app.py.bak
echo.
echo Close the MeriWatch window if it is still open,
echo then press any key to start it.
pause >nul
start "" run.bat
