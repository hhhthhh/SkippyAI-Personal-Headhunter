#!/bin/bash

# Ensure the script runs in the directory it's located in
cd "$(dirname "$0")"

echo "======================================================="
echo "             Skippy - Mac/Linux Bootstrapper"
echo "======================================================="
echo ""
echo "DISCLAIMER:"
echo "To run Skippy without requiring manual setup, this script will:"
echo " 1. Verify Python 3 is installed."
echo " 2. Create a secure, isolated virtual environment."
echo " 3. Install critical dependencies (Streamlit, Playwright, etc.)."
echo ""

read -p "Do you wish to proceed with the setup and launch? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation aborted by user. Exiting..."
    exit 1
fi

echo ""

# STEP 1: Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "[Error] Python 3 could not be found."
    echo "Please install Python 3 ('brew install python3' on Mac, or 'sudo apt install python3' on Linux) and try again."
    exit 1
fi

# STEP 2: Create the virtual environment and install dependencies
if [ ! -d "venv" ]; then
    echo "[1/4] Building isolated application environment..."
    
    # Attempt to create venv, gracefully fail with instructions for Debian/Ubuntu
    if ! python3 -m venv venv; then
        echo ""
        echo "[Error] Failed to create virtual environment."
        echo "If you are on Ubuntu/Debian/WSL, you likely need to install the venv package."
        echo "Please run: sudo apt update && sudo apt install python3-venv -y"
        exit 1
    fi
    
    echo "[2/4] Installing application dependencies..."
    source venv/bin/activate
    python3 -m pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    
    echo "[3/4] Fetching web drivers and system dependencies for the scraper..."
    playwright install chromium
    
    # Check if the OS is Linux to run the OS-level dependency installer
    if [ "$(uname)" == "Linux" ]; then
        echo "Installing missing Linux system libraries for Chromium (requires sudo)..."
        python3 -m playwright install-deps chromium
    fi

else
    echo "[OK] Application dependencies verified."
    source venv/bin/activate
fi

# STEP 3: Launch the application
echo ""
echo "[4/4] Starting the Streamlit server..."

# Suppress the Streamlit Welcome/Email prompt permanently
mkdir -p "$HOME/.streamlit"
echo "[general]" > "$HOME/.streamlit/credentials.toml"
echo 'email = ""' >> "$HOME/.streamlit/credentials.toml"

streamlit run app.py --browser.gatherUsageStats=false