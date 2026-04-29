@echo off
echo Installing libraries...
pip install flask requests curl_cffi cryptography pystray Pillow pywebview pyinstaller

echo Building .exe...
pyinstaller --onefile --windowed --name "MeriWatch" ^
  --hidden-import pystray._win32 ^
  --hidden-import PIL._imaging ^
  --hidden-import webview ^
  --hidden-import webview.platforms.winforms ^
  --hidden-import clr ^
  --collect-all curl_cffi ^
  --collect-all webview ^
  app.py

echo Done!
if exist "dist\MeriWatch.exe" (
    echo SUCCESS: dist\MeriWatch.exe
    echo.
    echo Share the dist folder contents with others.
) else (
    echo FAILED: Check errors above
)
pause
