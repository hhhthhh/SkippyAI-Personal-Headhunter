@echo off
title Skippy - Docker Deployment
color 0A
cd /d "%~dp0"

echo =======================================================
echo          Skippy - Windows Docker One-Click Launch
echo =======================================================
echo.

:: 1. Verify Docker is installed
where docker >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed on this system!
    echo.
    echo Please download and install Docker Desktop for Windows:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

:: 2. Verify Docker daemon is running
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [NOTICE] Docker is installed, but Docker Desktop is not running.
    echo.
    echo Please start Docker Desktop from your Start Menu.
    echo Wait until the whale icon in your taskbar says "Docker Desktop is running",
    echo then press any key below to continue.
    echo.
    pause
    docker info >nul 2>&1
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Docker Desktop is still not running. Please start it and try again.
        pause
        exit /b 1
    )
)

:: 3. Detect modern 'docker compose' vs legacy 'docker-compose'
set DOCKER_COMPOSE=docker compose
docker compose version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    set DOCKER_COMPOSE=docker-compose
)

:: 4. Pre-create persistence files so Docker won't create directories
if not exist "skippy.db" type nul > "skippy.db"
if not exist ".env" type nul > ".env"
if not exist "resume.md" type nul > "resume.md"
if not exist "resumes.json" echo {} > "resumes.json"
if not exist "custom_prompt.txt" type nul > "custom_prompt.txt"
if not exist "inbox.json" echo [] > "inbox.json"
if not exist "prompt_presets.json" echo {} > "prompt_presets.json"

echo Building and starting the Skippy container...
%DOCKER_COMPOSE% up -d --build
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start Docker container.
    pause
    exit /b 1
)

echo.
echo Waiting for Skippy web interface to start...
timeout /t 3 >nul

echo.
echo =======================================================
echo  [ RUNNING ] SKIPPY IS NOW LIVE IN DOCKER!
echo.
echo  Dashboard: http://localhost:8501
echo.
echo  To stop Skippy later, open this folder in terminal
echo  and run: %DOCKER_COMPOSE% down
echo =======================================================
echo.

:: Automatically open default web browser
start http://localhost:8501

timeout /t 5 >nul
exit