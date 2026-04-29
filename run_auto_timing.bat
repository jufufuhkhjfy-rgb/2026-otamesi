@echo off
cd /d "%~dp0"
python -m pip install pyautogui numpy Pillow mss pynput -q
start pythonw auto_timing.py
