@echo off
chcp 65001 > nul
echo ========================================
echo  AI株式デイトレードシミュレーター
echo ========================================
echo.

REM ANTHROPIC_API_KEY が設定されているか確認
if "%ANTHROPIC_API_KEY%"=="" (
    echo [警告] ANTHROPIC_API_KEY が設定されていません
    echo Claude AI の代わりにルールベース取引が使われます
    echo.
    set /p APIKEY="APIキーを今すぐ入力する場合はここに貼り付け（不要ならEnter）: "
    if not "%APIKEY%"=="" (
        set ANTHROPIC_API_KEY=%APIKEY%
    )
)

echo.
echo 起動中... ブラウザで http://localhost:5001 を開いてください
echo 終了するには Ctrl+C を押してください
echo.
python trader_app.py
pause
