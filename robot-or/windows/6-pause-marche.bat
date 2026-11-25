@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if exist PAUSE.flag (
  del PAUSE.flag
  echo Robot REMIS EN MARCHE : il reprendra les entrees au prochain range.
) else (
  echo pause > PAUSE.flag
  echo Robot EN PAUSE : plus aucune nouvelle entree. Les positions ouvertes gardent leur stop et leur objectif.
)
pause
