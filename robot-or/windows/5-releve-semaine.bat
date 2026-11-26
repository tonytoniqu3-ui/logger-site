@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call "%~dp0_preparer.bat" || exit /b 1
python releve.py
