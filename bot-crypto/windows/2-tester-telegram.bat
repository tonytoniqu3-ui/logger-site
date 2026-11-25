@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
set PYTHONUTF8=1
python bot.py telegram
pause
