@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM ============================================================
REM  納品用 exe ビルド
REM
REM  案件ごとに変えるのは下の PRODUCT_NAME だけ。
REM  build.bat（MeriWatch用）をパラメータ化したもの。
REM
REM  出力: dist\<PRODUCT_NAME>.exe
REM  顧客には exe と config.json の2ファイルを渡す。
REM ============================================================

set "PRODUCT_NAME=%~1"
if "%PRODUCT_NAME%"=="" set "PRODUCT_NAME=AutoWatch"

REM このバッチは toolkit\ にあるので、1つ上（プロジェクトルート）で作業する
cd /d "%~dp0.." || exit /b 1

echo ============================================
echo  Building: %PRODUCT_NAME%
echo ============================================
echo.

echo [1/4] Checking Python...
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (set "PY=py -3") else (set "PY=python")

echo [2/4] Installing dependencies...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r toolkit\requirements.txt pyinstaller
if errorlevel 1 (
    echo FAILED: Dependency installation failed.
    pause & exit /b 1
)

REM 第2引数に debug を渡すとコンソール版になる。
REM --windowed だとエラーが画面に出ないまま落ちるので、原因調査はこちらで行う。
set "WINMODE=--windowed"
if /i "%~2"=="debug" set "WINMODE=--console"

echo [3/4] Building .exe... (%WINMODE%)
if not exist "dist" mkdir dist
%PY% -m PyInstaller --noconfirm --clean --onefile %WINMODE% ^
  --name "%PRODUCT_NAME%" --distpath dist ^
  --hidden-import bs4 ^
  --hidden-import webview ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import clr ^
  --collect-all webview ^
  --collect-data certifi ^
  run_tool.py
if errorlevel 1 (
    echo FAILED: Build failed.
    pause & exit /b 1
)

echo [4/4] Preparing delivery folder...
REM config.json は exe と同じ場所に置く（watcher.py の BASE_DIR 参照）
if not exist "dist\config.json" (
    if exist "config.json" (
        copy /y "config.json" "dist\config.json" >nul
    ) else (
        copy /y "toolkit\config.example.json" "dist\config.json" >nul
    )
)

echo.
if exist "dist\%PRODUCT_NAME%.exe" (
    echo SUCCESS: dist\%PRODUCT_NAME%.exe
    echo.
    echo === 納品前チェック ===
    echo  1. Python が入っていない PC で起動すること
    echo  2. dist\config.json を顧客の設定に書き換えること
    echo  3. 通知先 ^(Discord Webhook / メール^) が顧客のものになっていること
    echo  4. data\ フォルダを空にしてから渡すこと ^(テストデータの混入防止^)
) else (
    echo FAILED: Check errors above
)
pause
