@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo === 30 dernieres lignes de bot.log ===
powershell -NoProfile -Command "Get-Content -Path bot.log -Tail 30 -Encoding UTF8"
echo.
if exist state\journal_paper.csv (echo === Journal simulation === & type state\journal_paper.csv)
if exist state\journal_live.csv (echo === Journal reel === & type state\journal_live.csv)
pause
