@echo off
cd /d "%~dp0"
python -m pip install pynput numpy Pillow mss -q
start pythonw medal_clicker.py
