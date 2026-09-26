@echo off
title Skippy - Windows Deployment
color 0A

:: Ensure the script runs in the current directory
cd /d "%~dp0"

echo =======================================================
echo               Skippy - Windows Bootstrapper
echo =======================================================
echo.
echo DISCLAIMER:
echo To run Skippy without requiring manual setup, this script will check
echo for the necessary components within this folder. If missing, it will:
echo  1. Automatically download a completely isolated Python 3.11 engine.
echo  2. Create a secure, isolated virtual environment.
echo  3. Install critical dependencies (Streamlit, Playwright, etc.).
echo.
echo This process does NOT require Administrator privileges and will NOT 
echo interfere with any global Python installations on your computer.
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

:: Check if portable Python is already downloaded
IF EXIST "python_runtime\tools\python.exe" GOTO CheckVenv

echo [1/5] Downloading portable Python 3.11 engine...
curl -# -L -o python_portable.zip https://www.nuget.org/api/v2/package/python/3.11.9

echo [2/5] Extracting Python natively (bypassing system installers)...
powershell -command "Expand-Archive -Path 'python_portable.zip' -DestinationPath 'python_runtime' -Force"
del python_portable.zip

:CheckVenv
:: Check if virtual environment already exists
IF EXIST "venv\Scripts\python.exe" GOTO LaunchApp

echo [3/5] Building isolated application environment...
"python_runtime\tools\python.exe" -m venv venv

echo [4/5] Installing application dependencies...
call "venv\Scripts\activate.bat"
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo [5/5] Fetching web drivers for the scraper...
playwright install chromium

echo.
echo Initial setup complete! Go to http://localhost:8501 to use Skippy!

:LaunchApp
echo.
echo Starting the Streamlit server...
call "venv\Scripts\activate.bat"

:: Suppress the Streamlit Welcome/Email prompt permanently
mkdir "%USERPROFILE%\.streamlit" 2>nul
echo [general] > "%USERPROFILE%\.streamlit\credentials.toml"
echo email = "" >> "%USERPROFILE%\.streamlit\credentials.toml"

streamlit run app.py --browser.gatherUsageStats=false

pause