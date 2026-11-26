@echo off
rem Prepare l'environnement Python s'il manque (appele par les autres fichiers .bat)
if exist .venv\Scripts\activate.bat goto pret
echo Premiere utilisation de ce dossier : installation des bibliotheques (2 a 3 minutes)...
where python >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installe-le depuis python.org en cochant "Add python.exe to PATH".
  pause
  exit /b 1
)
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
:pret
call .venv\Scripts\activate.bat
set PYTHONUTF8=1
exit /b 0
