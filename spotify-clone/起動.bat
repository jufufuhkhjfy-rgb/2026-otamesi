@echo off
chcp 65001 > nul
echo Music Player を起動しています...

cd /d "%~dp0"

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo Node.js がインストールされていません。
    echo https://nodejs.org からインストールしてください。
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo 初回起動: パッケージをインストール中...
    npm install
)

npm start
