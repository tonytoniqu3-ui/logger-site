@echo off
chcp 65001 >nul
title Bot crypto - SIMULATION
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
set PYTHONUTF8=1
:boucle
echo [%date% %time%] Demarrage du bot en SIMULATION (argent fictif). Ferme cette fenetre pour l'arreter.
python bot.py paper
echo [%date% %time%] Le bot s'est arrete. Redemarrage dans 60 secondes...
timeout /t 60 /nobreak >nul
goto boucle
