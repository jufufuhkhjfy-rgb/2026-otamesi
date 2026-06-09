@echo off
chcp 65001 >nul 2>&1
echo ================================
echo  Music Player アップデーター
echo ================================
echo.
echo 最新ファイルをダウンロード中...

cd /d "%~dp0"

set BASE=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone

powershell -Command "Invoke-WebRequest '%BASE%/main.js' -OutFile 'main.js'" 2>nul
powershell -Command "Invoke-WebRequest '%BASE%/renderer.js' -OutFile 'renderer.js'" 2>nul
powershell -Command "Invoke-WebRequest '%BASE%/preload.js' -OutFile 'preload.js'" 2>nul
powershell -Command "Invoke-WebRequest '%BASE%/index.html' -OutFile 'index.html'" 2>nul
powershell -Command "Invoke-WebRequest '%BASE%/styles.css' -OutFile 'styles.css'" 2>nul
powershell -Command "Invoke-WebRequest '%BASE%/firebase.js' -OutFile 'firebase.js'" 2>nul
powershell -Command "Invoke-WebRequest '%BASE%/package.json' -OutFile 'package.json'" 2>nul

echo ダウンロード完了！
echo.
echo ビルド中... (2〜3分かかります)
echo.

call npm run build

if %errorlevel% == 0 (
  echo.
  echo ================================
  echo  完了！
  echo  dist\win-unpacked が最新です
  echo  ZIPにして友達に送ってください
  echo ================================
) else (
  echo.
  echo エラーが発生しました。
)

pause
