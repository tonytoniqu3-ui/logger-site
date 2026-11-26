@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo === Installation du bot crypto ===
where python >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installe-le depuis python.org en cochant "Add python.exe to PATH", puis relance ce fichier.
  pause
  exit /b 1
)
python --version
if not exist .venv (
  echo Creation de l'environnement virtuel...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo L'installation des bibliotheques a echoue. Verifie ta connexion internet et relance.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
echo.
echo === Verification : les tests ===
python -m pytest -q
echo.
echo === Verification : le bot sur les vraies donnees Coinbase ===
python bot.py portfolio
echo.
echo Installation terminee. Etape suivante : 2-tester-telegram.bat (voir GUIDE-WINDOWS.md).
pause
