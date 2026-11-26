@echo off
chcp 65001 >nul
echo Ce fichier fait demarrer le bot tout seul a chaque ouverture de session Windows.
echo.
echo   S = simulation (argent fictif)
echo   R = argent reel
echo   A = annuler le demarrage automatique
echo.
set /p MODE=Ton choix (S, R ou A) : 
if /i "%MODE%"=="A" (
  schtasks /delete /tn "BotCrypto" /f
  pause
  exit /b 0
)
if /i "%MODE%"=="S" set CIBLE=%~dp03-lancer-simulation.bat
if /i "%MODE%"=="R" set CIBLE=%~dp05-lancer-reel.bat auto
if not defined CIBLE (
  echo Choix inconnu.
  pause
  exit /b 1
)
schtasks /create /tn "BotCrypto" /tr "cmd /c \"%CIBLE%\"" /sc onlogon /f
if errorlevel 1 (
  echo Echec. Fais un clic droit sur ce fichier puis "Executer en tant qu'administrateur".
) else (
  echo C'est fait : le bot demarrera a chaque ouverture de session.
)
pause
