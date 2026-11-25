@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
set PYTHONUTF8=1
echo Simulation de la strategie sur l'historique (500 euros de depart)...
python simuler.py
