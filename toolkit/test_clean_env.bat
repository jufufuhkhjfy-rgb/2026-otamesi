@echo off
setlocal
title Clean environment test

REM ---------------------------------------------------------------
REM  Start the exe with Python removed from PATH.
REM
REM  Two rules for this file (same as mw_update.bat):
REM   1) ASCII only. cmd.exe reads .bat in the system codepage
REM      (CP932 on Japanese Windows), so UTF-8 Japanese turns into
REM      garbage and gets executed as commands.
REM   2) No multi-line ( ) blocks. GitHub raw may serve this file
REM      with LF endings, and cmd.exe mis-parses blocks that span
REM      lines. Every conditional below stays on a single line.
REM
REM  Windows Home has no Sandbox, so this is the next best check.
REM  A PyInstaller onefile exe carries its own interpreter and never
REM  reads the system site-packages, so this catches most problems.
REM  It is not proof: run it once on a PC without Python before
REM  selling anything.
REM
REM  Usage:  test_clean_env.bat [ProductName]
REM ---------------------------------------------------------------

set PRODUCT=%~1
if "%PRODUCT%"=="" set PRODUCT=AutoWatch

cd /d "%~dp0.."

if not exist "dist\%PRODUCT%.exe" echo. & echo [NG] dist\%PRODUCT%.exe not found. Run toolkit\build_exe.bat first. & echo. & pause & exit /b 1

echo ============================================
echo   Clean environment test: %PRODUCT%
echo ============================================
echo.

REM Copy elsewhere so we also catch any hidden dependency on files
REM that only exist inside this folder.
set TESTDIR=%TEMP%\%PRODUCT%_cleantest
if exist "%TESTDIR%" rmdir /s /q "%TESTDIR%"
mkdir "%TESTDIR%"
copy /y "dist\%PRODUCT%.exe" "%TESTDIR%\" >nul
if exist dist\config.json copy /y dist\config.json "%TESTDIR%\config.json" >nul
if not exist "%TESTDIR%\config.json" copy /y toolkit\config.example.json "%TESTDIR%\config.json" >nul
echo Copied to: %TESTDIR%
echo.

REM Make Python unreachable.
set PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem
set PYTHONPATH=
set PYTHONHOME=
set PYTHONSTARTUP=

where python >nul 2>&1
if errorlevel 1 echo [OK] python is not on PATH
if not errorlevel 1 echo [NG] python is still reachable
where py >nul 2>&1
if errorlevel 1 echo [OK] py is not on PATH
if not errorlevel 1 echo [NG] py is still reachable
echo.

echo Starting. A window should open.
echo Press the start button in the app and watch the log fill up.
echo.
pushd "%TESTDIR%"
"%PRODUCT%.exe"
set RC=%ERRORLEVEL%
popd

echo.
echo Exit code: %RC%
echo.
if not "%RC%"=="0" echo [NG] It crashed. --windowed hides the error, so rebuild a console version to read it:
if not "%RC%"=="0" echo      toolkit\build_exe.bat %PRODUCT% debug
if "%RC%"=="0" echo [OK] Finished without an error code.
echo.
pause
exit /b 0
