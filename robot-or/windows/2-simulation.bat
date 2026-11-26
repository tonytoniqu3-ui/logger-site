@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call "%~dp0_preparer.bat" || exit /b 1
echo Simulation de la strategie sur l'historique (500 euros de depart)...
python simuler.py
