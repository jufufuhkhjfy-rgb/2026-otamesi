@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul

echo ================================
echo  自動化ツールキット 取り込み
echo ================================
echo.
echo GitHub から最新のファイルを取ってきます。
echo.

REM ブラウザ経由だとキャッシュされた古い内容を掴むため、
REM no-cache ヘッダを付けて curl で直接取得する（update_meriwatch.bat と同じやり方）
set H=-H "Cache-Control: no-cache" -H "Pragma: no-cache"
set BASE=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main

if not exist toolkit mkdir toolkit

set FAILED=0

call :get "run_tool.py"                  "run_tool.py"
call :get "toolkit/__init__.py"          "toolkit\__init__.py"
call :get "toolkit/store.py"             "toolkit\store.py"
call :get "toolkit/sources.py"           "toolkit\sources.py"
call :get "toolkit/notify.py"            "toolkit\notify.py"
call :get "toolkit/watcher.py"           "toolkit\watcher.py"
call :get "toolkit/dashboard.py"         "toolkit\dashboard.py"
call :get "toolkit/requirements.txt"     "toolkit\requirements.txt"
call :get "toolkit/config.example.json"  "toolkit\config.example.json"
call :get "toolkit/build_exe.bat"        "toolkit\build_exe.bat"
call :get "toolkit/test_clean_env.bat"   "toolkit\test_clean_env.bat"
call :get "toolkit/README.md"            "toolkit\README.md"

echo.
if not "%FAILED%"=="0" (
    echo -------------------------------------------
    echo  %FAILED% 個のファイルが取れませんでした。
    echo  ネット接続を確認して、もう一度実行してください。
    echo -------------------------------------------
    pause
    exit /b 1
)

echo ===========================================
echo  取り込み完了
echo ===========================================
echo.
echo 次にやること:
echo.
echo   1. toolkit\build_exe.bat をダブルクリック
echo      → アプリ本体 ^(dist\AutoWatch.exe^) ができます。数分かかります。
echo.
echo   2. toolkit\test_clean_env.bat をダブルクリック
echo      → ちゃんと動くか確認します。
echo.
pause
exit /b 0


:get
REM %1 = GitHub上のパス, %2 = 保存先
curl -L -f -s %H% -o "%~2.new" "%BASE%/%~1"
if errorlevel 1 (
    echo   [NG] %~1
    del /q "%~2.new" 2>nul
    set /a FAILED+=1
    exit /b 0
)
for %%A in ("%~2.new") do set SIZE=%%~zA
if !SIZE! LSS 50 (
    echo   [NG] %~1 ^(中身が小さすぎます^)
    del /q "%~2.new" 2>nul
    set /a FAILED+=1
    exit /b 0
)
move /y "%~2.new" "%~2" >nul
echo   [OK] %~1  ^(!SIZE! バイト^)
exit /b 0
