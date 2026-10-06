@echo off
title Skippy - Local Server
color 0A

cd /d "%~dp0"

:: FAST BOOT: Skip setup if the environment is already built
IF EXIST "python_runtime\Scripts\streamlit.exe" GOTO LaunchApp

echo =======================================================
echo               Skippy - Windows Bootstrapper
echo =======================================================
echo.
echo DISCLAIMER:
echo To run Skippy without requiring manual setup, this script will:
echo  1. Download the official Python 3.11 Portable Zip.
echo  2. Configure it with PIP and required standard libraries.
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
:: Cleanup any failed previous attempts
del /q /f python_portable.zip 2>nul
rmdir /s /q python_runtime 2>nul

echo [1/5] Downloading Python 3.11 Portable (Embeddable)...
curl -# -L -o python_portable.zip https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip

echo [2/5] Extracting Python natively...
powershell -command "Expand-Archive -Path 'python_portable.zip' -DestinationPath 'python_runtime' -Force"
del python_portable.zip

echo [3/5] Configuring Python for application use (Enabling PIP)...
:: The portable version needs the 'site' module enabled to use pip
powershell -command "(Get-Content python_runtime\python311._pth) -replace '#import site', 'import site' | Set-Content python_runtime\python311._pth"
curl -# -L -o python_runtime\get-pip.py https://bootstrap.pypa.io/get-pip.py
"python_runtime\python.exe" "python_runtime\get-pip.py" --no-warn-script-location >nul

echo [4/5] Installing application dependencies...
"python_runtime\python.exe" -m pip install --quiet --upgrade pip
"python_runtime\python.exe" -m pip install --quiet -r requirements.txt

echo [5/5] Fetching web drivers for the scraper...
"python_runtime\Scripts\playwright.exe" install chromium

echo.
echo Initial setup complete!
GOTO LaunchApp

:: =======================================================
:: LAUNCH SEQUENCE (Runs every time)
:: =======================================================
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

"python_runtime\python.exe" -m streamlit run app.py --server.port=8501 --server.address=localhost --browser.gatherUsageStats=false