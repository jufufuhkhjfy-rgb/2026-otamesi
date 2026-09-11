@echo off
setlocal
cd /d "%~dp0"
title Medal Clicker Installer

REM ---------------------------------------------------------------
REM  Medal clicker installer - just double click it.
REM
REM  Two rules for this file (same as mw_update.bat):
REM   1) ASCII only. cmd.exe reads .bat in the system codepage
REM      (CP932 on Japanese Windows), so UTF-8 Japanese turns into
REM      garbage and gets executed as commands.
REM   2) No multi-line ( ) blocks. GitHub raw may serve this file
REM      with LF endings, and cmd.exe mis-parses blocks that span
REM      lines. Every conditional below stays on a single line.
REM
REM  This only writes medal_clicker.py and run_medal_clicker.bat.
REM  Recorded positions in medal_clicker.json are left alone.
REM ---------------------------------------------------------------

echo ================================
echo   Medal Clicker Installer
echo ================================
echo.
echo Downloading the latest files from GitHub ...
echo.

set BASE=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main
set NOCACHE=-H "Cache-Control: no-cache" -H "Pragma: no-cache"
set FAILED=0

call :get medal_clicker.py       medal_clicker.py       10000
call :get run_medal_clicker.bat  run_medal_clicker.bat  50

echo.
if not "%FAILED%"=="0" echo [NG] %FAILED% file(s) failed. Check your internet connection and run again. & echo. & pause & exit /b 1

echo Installing python packages ...
python -m pip install pynput numpy Pillow mss -q
if errorlevel 1 echo [NG] pip failed. Is Python installed and on PATH? & echo. & pause & exit /b 1

echo.
echo ===============================================
echo   [OK] Done.
echo ===============================================
echo.
echo   Next: double click  run_medal_clicker.bat
echo.
pause
exit /b 0

:get
REM %1 = path on GitHub, %2 = local destination, %3 = minimum bytes
curl -L -f -s -S %NOCACHE% -o "%~2.new" "%BASE%/%~1"
if errorlevel 1 echo   [NG] %~1 & del /q "%~2.new" 2>nul & set /a FAILED+=1 & exit /b 0
set SIZE=0
for %%A in ("%~2.new") do set SIZE=%%~zA
if %SIZE% LSS %~3 echo   [NG] %~1 - file too small: %SIZE% bytes & del /q "%~2.new" 2>nul & set /a FAILED+=1 & exit /b 0
move /y "%~2.new" "%~2" >nul
echo   [OK] %~1 - %SIZE% bytes
exit /b 0
