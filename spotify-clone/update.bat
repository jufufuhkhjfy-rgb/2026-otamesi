@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs -WorkingDirectory '%~dp0'"
  exit
)

echo ================================
echo  Music Player Updater
echo ================================
echo.
echo Downloading latest files...

set H=-H "Cache-Control: no-cache" -H "Pragma: no-cache"
set BASE=https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone

curl -L -f %H% -o main.js     "%BASE%/main.js"
curl -L -f %H% -o renderer.js "%BASE%/renderer.js"
curl -L -f %H% -o preload.js  "%BASE%/preload.js"
curl -L -f %H% -o index.html  "%BASE%/index.html"
curl -L -f %H% -o styles.css  "%BASE%/styles.css"
curl -L -f %H% -o firebase.js "%BASE%/firebase.js"
curl -L -f %H% -o package.json "%BASE%/package.json"

echo Download done!
echo.

rmdir /s /q "%LOCALAPPDATA%\electron-builder\Cache\winCodeSign" 2>nul

echo Building... (2-3 min)
echo.

set CSC_IDENTITY_AUTO_DISCOVERY=false
set WIN_CSC_LINK=
call npm run build

if %errorlevel% == 0 (
  echo.
  echo ================================
  echo  Done! dist\win-unpacked is ready
  echo ================================
) else (
  echo.
  echo Build failed.
)

pause
