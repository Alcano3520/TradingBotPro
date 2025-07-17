@echo off
title Instalador Trading Bot Pro
echo ================================
echo   INSTALADOR TRADING BOT PRO
echo ================================
echo.
echo Instalando dependencias...
echo.
pip install -r requirements.txt
echo.
if errorlevel 1 (
    echo ERROR: Fall? la instalaci?n de dependencias
    pause
    exit /b 1
)
echo.
echo ? Dependencias instaladas correctamente
echo.
echo Puede ejecutar el bot con: start_bot.bat
pause
