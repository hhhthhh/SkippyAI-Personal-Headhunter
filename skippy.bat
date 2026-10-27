@echo off
title Skippy - AI Job CRM
color 0A

cd /d "%~dp0"

:: FAST BOOT: Skip setup if the environment is already built
IF EXIST "python_runtime\Scripts\streamlit.exe" GOTO LaunchApp

echo =======================================================
echo          Skippy - Windows One-Click Installer
echo =======================================================
echo.
echo First-time setup detected. Setting up Skippy automatically...
echo This will take 1-2 minutes depending on your internet speed.
echo.

:: Clean up any incomplete previous attempts
del /q /f python_portable.zip 2>nul
rmdir /s /q python_runtime 2>nul

echo [1/5] Downloading portable Python runtime...
where curl >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    curl -# -L -o python_portable.zip https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
) ELSE (
    powershell -command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python_portable.zip'"
)

IF NOT EXIST python_portable.zip (
    echo.
    echo [ERROR] Failed to download Python. Please check your internet connection.
    pause
    exit /b 1
)

echo [2/5] Extracting Python files...
powershell -command "Expand-Archive -Path 'python_portable.zip' -DestinationPath 'python_runtime' -Force"
del /q /f python_portable.zip 2>nul

echo [3/5] Configuring package manager (pip)...
powershell -command "(Get-Content python_runtime\python311._pth) -replace '#import site', 'import site' | Set-Content python_runtime\python311._pth"

where curl >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    curl -s -L -o python_runtime\get-pip.py https://bootstrap.pypa.io/get-pip.py
) ELSE (
    powershell -command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python_runtime\get-pip.py'"
)

"python_runtime\python.exe" "python_runtime\get-pip.py" --no-warn-script-location >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to configure pip.
    pause
    exit /b 1
)
del /q /f "python_runtime\get-pip.py" 2>nul

echo [4/5] Installing application dependencies (this may take a moment)...
"python_runtime\python.exe" -m pip install --quiet --no-warn-script-location --upgrade pip
"python_runtime\python.exe" -m pip install --quiet --no-warn-script-location --default-timeout=120 --retries=5 -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install requirements. Please check your connection.
    pause
    exit /b 1
)

echo [5/5] Installing scraper browser driver (Chromium)...
"python_runtime\python.exe" -m playwright install chromium
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Playwright Chromium install had a warning, continuing setup...
)

echo.
echo Setup complete! Launching Skippy...
timeout /t 1 >nul
GOTO LaunchApp

:: =======================================================
:: LAUNCH SEQUENCE (Runs every time)
:: =======================================================
:LaunchApp
:: Suppress Streamlit email prompt and usage telemetry cleanly
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set LITELLM_DISABLE_REDACT_SECRETS=true
set LITELLM_LOCAL_MODEL_COST_MAP=True

:: Ensure template prompt files are initialized
if not exist "custom_prompt.txt" (
    if exist "custom_prompt.template.txt" (
        copy /y "custom_prompt.template.txt" "custom_prompt.txt" >nul
    )
)
if not exist "custom_user_prompt.txt" (
    if exist "custom_prompt.template.txt" (
        copy /y "custom_prompt.template.txt" "custom_user_prompt.txt" >nul
    )
)

mkdir "%USERPROFILE%\.streamlit" 2>nul
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo [general] > "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "" >> "%USERPROFILE%\.streamlit\credentials.toml"
)

cls
echo =======================================================
echo  [ RUNNING ] SKIPPY IS OPENING IN YOUR BROWSER!
echo.
echo  Dashboard: http://localhost:8501
echo.
echo  *** DO NOT CLOSE THIS WINDOW ***
echo  Minimize this window to the taskbar to keep Skippy on.
echo  When you are done, close this window to stop Skippy.
echo =======================================================
echo.

"python_runtime\python.exe" -m streamlit run app.py --server.port=8501 --server.address=localhost --server.headless=false --browser.gatherUsageStats=false

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [NOTE] Skippy stopped running.
    pause
)