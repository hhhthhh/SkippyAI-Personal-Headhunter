@echo off
title Skippy - Local Server
color 0A

:: Ensure the script runs in the current directory
cd /d "%~dp0"

:: FAST BOOT: Skip setup if virtual environment already exists
IF EXIST "venv\Scripts\python.exe" GOTO FastBoot

:: =======================================================
:: FIRST-TIME SETUP
:: =======================================================
echo =======================================================
echo               Skippy - Windows Bootstrapper
echo =======================================================
echo.
echo DISCLAIMER:
echo To run Skippy without requiring manual setup, this script will:
echo  1. Automatically download an isolated Python 3.11 engine.
echo  2. Create a secure, isolated virtual environment.
echo  3. Install critical dependencies (Streamlit, Playwright, etc.).
echo.
echo NOTE: You will need a valid AI API key (Gemini, OpenAI, GROK or Anthropic)
echo to use this application unless you are running a local Ollama model.
echo.

CHOICE /C YN /M "Do you wish to proceed with the setup and launch?"
IF ERRORLEVEL 2 GOTO AbortSetup
IF ERRORLEVEL 1 GOTO BeginSetup

:AbortSetup
echo.
echo Operation aborted by user. Exiting...
timeout /t 3 >nul
exit

:BeginSetup
echo.
IF EXIST "python_runtime\tools\python.exe" GOTO CheckVenv

:: Wipe any broken/incomplete zip files from previous interrupted attempts
del /q /f python_portable.zip 2>nul

echo [1/5] Downloading portable Python 3.11 engine...
curl -# -L -o python_portable.zip https://www.nuget.org/api/v2/package/python/3.11.9

echo [2/5] Extracting Python natively...
powershell -command "Expand-Archive -Path 'python_portable.zip' -DestinationPath 'python_runtime' -Force"
del python_portable.zip

:CheckVenv
echo [3/5] Building isolated application environment...
"python_runtime\tools\python.exe" -m venv venv

echo [4/5] Installing application dependencies...
call "venv\Scripts\activate.bat"
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo [5/5] Fetching web drivers for the scraper...
playwright install chromium

echo.
echo Initial setup complete!
GOTO LaunchApp

:: =======================================================
:: LAUNCH SEQUENCE (Runs every time)
:: =======================================================
:FastBoot
call "venv\Scripts\activate.bat"

:LaunchApp
:: Suppress the Streamlit Welcome/Email prompt permanently
mkdir "%USERPROFILE%\.streamlit" 2>nul
echo [general] > "%USERPROFILE%\.streamlit\credentials.toml"
echo email = "" >> "%USERPROFILE%\.streamlit\credentials.toml"

cls
echo =======================================================
echo  [ RUNNING ] SKIPPY IS OPENING IN YOUR BROWSER!
echo.
echo  *** DO NOT CLOSE THIS WINDOW ***
echo  Minimize it to the taskbar to keep Skippy running.
echo  When you are completely done, close this window to 
echo  turn the application off.
echo =======================================================
echo.

streamlit run app.py --browser.gatherUsageStats=false