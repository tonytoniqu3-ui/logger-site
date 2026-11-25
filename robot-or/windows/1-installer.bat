@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo === Installation du robot or ===
where python >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installe-le depuis python.org en cochant "Add python.exe to PATH", puis relance.
  pause
  exit /b 1
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo L'installation a echoue. Verifie ta connexion internet et relance.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
echo.
echo === Verification : les tests ===
python -m pytest -q tests
echo.
echo Installation terminee. Etape suivante : 2-simulation.bat puis 3-lancer-robot.bat
pause
