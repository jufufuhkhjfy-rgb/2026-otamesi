@echo off
setlocal
chcp 65001 >nul

REM ============================================================
REM  クリーン環境での起動テスト
REM
REM  Windows Home にはサンドボックスが無いため、
REM  「PATH から Python を消した状態」を作って exe を起動する。
REM
REM  PyInstaller の onefile exe は自分の中にインタプリタとライブラリを
REM  抱えていて、システムの site-packages は読まない。
REM  そのため、この方法でも「開発環境に依存していないか」はかなり確認できる。
REM
REM  ただし完全ではない。売り始める前に一度は、
REM  Python の入っていない別のPCで動かして確かめること。
REM
REM  使い方:  toolkit\test_clean_env.bat [製品名]
REM ============================================================

cd /d "%~dp0.." || exit /b 1

set "EXE=%~1"
if "%EXE%"=="" set "EXE=AutoWatch"

if not exist "dist\%EXE%.exe" (
    echo.
    echo dist\%EXE%.exe が見つかりません。
    echo 先に次を実行してください:  toolkit\build_exe.bat %EXE%
    echo.
    pause & exit /b 1
)

echo ============================================
echo  クリーン環境テスト: %EXE%
echo ============================================
echo.

REM 別フォルダにコピーして動かす。
REM リポジトリの中のファイルを勝手に参照していないかを洗い出すため。
set "TESTDIR=%TEMP%\%EXE%_cleantest"
if exist "%TESTDIR%" rmdir /s /q "%TESTDIR%"
mkdir "%TESTDIR%"
copy /y "dist\%EXE%.exe" "%TESTDIR%\" >nul
if exist "dist\config.json" (
    copy /y "dist\config.json" "%TESTDIR%\config.json" >nul
) else (
    copy /y "toolkit\config.example.json" "%TESTDIR%\config.json" >nul
)
echo コピー先: %TESTDIR%
echo.

REM Python を参照できない環境にする
set "PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem"
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONSTARTUP="

where python >nul 2>&1 && (echo [NG] まだ python が見つかります) || (echo [OK] python は PATH にありません)
where py     >nul 2>&1 && (echo [NG] まだ py が見つかります)     || (echo [OK] py は PATH にありません)
echo.

echo 起動します。画面が開いて「監視開始」で動けば合格です。
echo.
pushd "%TESTDIR%"
"%EXE%.exe"
set "RC=%ERRORLEVEL%"
popd

echo.
echo 終了コード: %RC%
echo.
if not "%RC%"=="0" (
    echo -------------------------------------------
    echo  異常終了しました。
    echo  --windowed だとエラーが表示されないため、
    echo  次でコンソール版を作り直すと原因が読めます:
    echo.
    echo     toolkit\build_exe.bat %EXE% debug
    echo -------------------------------------------
)
pause
