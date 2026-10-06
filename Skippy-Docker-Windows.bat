@echo off
title Skippy - Docker Deployment
color 0A
cd /d "%~dp0"

echo =======================================================
echo               Skippy - Docker Bootstrapper
echo =======================================================
echo.
echo NOTE: You will need a valid AI API key (Gemini, OpenAI, GROK or Anthropic)
echo to use this application unless you are running a local Ollama model.
echo.
echo If you are prompted, click YES to ALLOW PYTHON to run on your machine!
echo Building and starting the Skippy container...
docker-compose up -d --build

echo.
echo Container is running! Opening your web browser...

:: Force the default browser to open
start http://localhost:8501

:: Exit the terminal automatically
exit