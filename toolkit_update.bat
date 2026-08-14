@echo off
setlocal
cd /d "%~dp0"
title Toolkit Updater

REM ---------------------------------------------------------------
REM  Toolkit updater - just double click it.
REM
REM  Two rules for this file (same as mw_update.bat):
REM   1) ASCII only. cmd.exe reads .bat in the system codepage
REM      (CP932 on Japanese Windows), so UTF-8 Japanese turns into
REM      garbage and gets executed as commands.
REM   2) No multi-line ( ) blocks. GitHub raw may serve this file
REM      with LF endings, and cmd.exe mis-parses blocks that span
REM      lines. Every conditional below stays on a single line.
REM
REM  This only writes run_tool.py and the toolkit folder.
REM  It never touches app.py or any other MeriWatch file.
REM ---------------------------------------------------------------

echo ================================
echo   Toolkit Updater
echo ================================
echo.
echo Downloading the latest files from GitHub ...
echo.

set BASE=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main
set NOCACHE=-H "Cache-Control: no-cache" -H "Pragma: no-cache"
set FAILED=0

if not exist toolkit mkdir toolkit

call :get run_tool.py                 run_tool.py
call :get toolkit/__init__.py         toolkit\__init__.py
call :get toolkit/store.py            toolkit\store.py
call :get toolkit/sources.py          toolkit\sources.py
call :get toolkit/notify.py           toolkit\notify.py
call :get toolkit/watcher.py          toolkit\watcher.py
call :get toolkit/dashboard.py        toolkit\dashboard.py
call :get toolkit/requirements.txt    toolkit\requirements.txt
call :get toolkit/config.example.json toolkit\config.example.json
call :get toolkit/build_exe.bat       toolkit\build_exe.bat
call :get toolkit/test_clean_env.bat  toolkit\test_clean_env.bat
call :get toolkit/README.md           toolkit\README.md

echo.
if not "%FAILED%"=="0" echo [NG] %FAILED% file(s) failed. Check your internet connection and run again. & echo. & pause & exit /b 1

echo ===============================================
echo   [OK] Done.
echo ===============================================
echo.
echo   Next: double click  toolkit\build_exe.bat
echo.
pause
exit /b 0

:get
REM %1 = path on GitHub, %2 = local destination
curl -L -f -s -S %NOCACHE% -o "%~2.new" "%BASE%/%~1"
if errorlevel 1 echo   [NG] %~1 & del /q "%~2.new" 2>nul & set /a FAILED+=1 & exit /b 0
set SIZE=0
for %%A in ("%~2.new") do set SIZE=%%~zA
if %SIZE% LSS 50 echo   [NG] %~1 - file too small & del /q "%~2.new" 2>nul & set /a FAILED+=1 & exit /b 0
move /y "%~2.new" "%~2" >nul
echo   [OK] %~1
exit /b 0
