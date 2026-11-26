@echo off
chcp 65001 >nul
title Bot crypto - ARGENT REEL
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
set PYTHONUTF8=1
if not "%1"=="auto" (
  echo ATTENTION : le bot va passer de VRAIS ordres sur Coinbase avec ton argent.
  echo Budget du bot : valeur "capital" dans config.json. Il ne touche a rien d'autre.
  set /p OK=Tape OUI en majuscules pour continuer : 
)
if not "%1"=="auto" if not "%OK%"=="OUI" (
  echo Annule.
  pause
  exit /b 1
)
:boucle
echo [%date% %time%] Demarrage du bot en ARGENT REEL. Ferme cette fenetre pour l'arreter.
python bot.py live --yes-real-money
echo [%date% %time%] Le bot s'est arrete. Redemarrage dans 60 secondes...
timeout /t 60 /nobreak >nul
goto boucle
