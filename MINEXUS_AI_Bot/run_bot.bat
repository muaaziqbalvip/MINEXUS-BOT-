@echo off
title Quotex Pro AI Telegram Bot
color 0A

echo.
echo  =======================================================
echo    QUOTEX PRO AI TELEGRAM SIGNAL ANALYZER BOT  v2.0
echo  =======================================================
echo.

python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo  [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo  Starting Quotex AI Telegram Bot Service...
echo.
python main.py

pause
