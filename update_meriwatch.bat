@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ================================
echo  MeriWatch アップデート
echo ================================
echo.

if not exist run.bat (
  echo このファイルは MeriWatch フォルダーに置いて実行してください。
  echo 今の場所: %CD%
  pause
  exit /b 1
)

REM ブラウザ経由だとキャッシュされた古い内容を掴むため、
REM no-cache ヘッダを付けて curl で直接取得する
set H=-H "Cache-Control: no-cache" -H "Pragma: no-cache"
set URL=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/app.py

echo 最新の app.py を取得しています...
curl -L -f %H% -o app.py.new "%URL%"
if errorlevel 1 (
  echo.
  echo 取得に失敗しました。ネット接続を確認してください。
  del /q app.py.new 2>nul
  pause
  exit /b 1
)

REM 取得した中身が壊れていないか、大きさで簡易確認する
for %%A in (app.py.new) do set SIZE=%%~zA
if %SIZE% LSS 50000 (
  echo.
  echo 取得したファイルが小さすぎます ^(%SIZE% バイト^)。中断しました。
  del /q app.py.new 2>nul
  pause
  exit /b 1
)

REM 差し替え前に現物を退避しておく。設定や購入履歴には触れない
if exist app.py copy /y app.py app.py.bak >nul
move /y app.py.new app.py >nul

echo.
echo 更新しました： %SIZE% バイト
echo 元のファイルは app.py.bak に残しています。
echo.
echo MeriWatch が起動中の場合は、先にウィンドウを閉じてください。
echo 閉じたら Enter を押すと起動します。
pause >nul
start "" run.bat
