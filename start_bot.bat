@echo off
title Trading Bot Pro
cls
echo ================================
echo    TRADING BOT PRO LAUNCHER
echo ================================
echo.
echo Verificando Python...
python --version
if errorlevel 1 (
    echo ERROR: Python no est? instalado o no est? en PATH
    pause
    exit /b 1
)
echo.
echo Iniciando Trading Bot Pro...
echo.
cd /d "%~dp0"
python main.py
echo.
echo Bot detenido.
pause
