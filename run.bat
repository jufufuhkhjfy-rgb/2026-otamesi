@echo off
pip install flask requests curl_cffi cryptography pystray Pillow pywebview anthropic -q
start "" pythonw app.py
