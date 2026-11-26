@echo off
chcp 65001 >nul
echo Le robot demarrera tout seul a chaque ouverture de session Windows.
echo   O = oui, activer
echo   A = annuler le demarrage automatique
set /p MODE=Ton choix (O ou A) : 
if /i "%MODE%"=="A" (
  schtasks /delete /tn "RobotOr" /f
  pause
  exit /b 0
)
if /i not "%MODE%"=="O" (
  echo Choix inconnu.
  pause
  exit /b 1
)
schtasks /create /tn "RobotOr" /tr "cmd /c \"%~dp03-lancer-robot.bat\"" /sc onlogon /delay 0002:00 /f
if errorlevel 1 (
  echo Echec. Clic droit sur ce fichier puis "Executer en tant qu'administrateur".
) else (
  echo C'est fait. Pense aussi a mettre MetaTrader 5 dans le demarrage automatique de Windows.
)
pause
