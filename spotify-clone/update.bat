@echo off
setlocal
cd /d "%~dp0"
echo ================================
echo  Music Player Updater
echo ================================
echo.
echo Downloading latest files...

curl -L -s -o main.js "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/main.js"
curl -L -s -o renderer.js "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/renderer.js"
curl -L -s -o preload.js "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/preload.js"
curl -L -s -o index.html "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/index.html"
curl -L -s -o styles.css "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/styles.css"
curl -L -s -o firebase.js "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/firebase.js"
curl -L -s -o package.json "https://raw.githubusercontent.com/jufufuhkhjfy-rgb/2026-otamesi/main/spotify-clone/package.json"

echo Download done!
echo.
echo Building... (2-3 min)
echo.

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
