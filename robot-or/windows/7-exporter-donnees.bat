@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
set PYTHONUTF8=1
echo Export de l'historique M5 depuis MetaTrader 5 (lecture seule, aucun ordre).
echo Le robot peut continuer a tourner pendant ce temps.
python exporter_donnees.py
explorer /select,"%cd%\export_donnees.zip"
pause
