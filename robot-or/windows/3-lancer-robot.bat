@echo off
chcp 65001 >nul
title Robot or - COMPTE DEMO
cd /d "%~dp0.."
call "%~dp0_preparer.bat" || exit /b 1
:boucle
echo [%date% %time%] Demarrage du robot or (compte DEMO). Ferme cette fenetre pour l'arreter.
python lancer_robot.py
if errorlevel 2 (
  echo.
  echo Le robot s'est arrete volontairement : lis le message ci-dessus.
  pause
  exit /b 2
)
echo [%date% %time%] Le robot s'est arrete. Redemarrage dans 60 secondes...
timeout /t 60 /nobreak >nul
goto boucle
