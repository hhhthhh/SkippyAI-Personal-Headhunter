#!/bin/bash

# Ensure the script runs in the directory it's located in
cd "$(dirname "$0")"

# FAST BOOT: Check if the virtual environment is already built
if [ ! -d "venv" ]; then
    # =======================================================
    # FIRST-TIME SETUP
    # =======================================================
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
    echo "NOTE: You will need a valid AI API key (Gemini, OpenAI, GROK or Anthropic)"
    echo "to use this application unless you are running a local Ollama model."
    echo ""

    read -p "Do you wish to proceed with the setup and launch? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Operation aborted by user. Exiting..."
        exit 1
    fi
    echo ""

    if ! command -v python3 &> /dev/null; then
        echo "[Error] Python 3 could not be found."
        echo "Please install Python 3 ('brew install python3' on Mac, or 'sudo apt install python3' on Linux) and try again."
        exit 1
    fi

    echo "[1/4] Building isolated application environment..."
    if ! python3 -m venv venv; then
        echo ""
        echo "[Error] Failed to create virtual environment."
        echo "If you are on Ubuntu/Debian/WSL, you likely need to install the venv package."
        echo "Please run: sudo apt update && sudo apt install python3-venv -y"
        exit 1
    fi
    
    echo "[2/4] Installing application dependencies..."
    source venv/bin/activate
    python3 -m pip install --upgrade pip
    pip install -r requirements.txt
    
    echo "[3/4] Fetching web drivers and system dependencies for the scraper..."
    playwright install chromium
    
    if [ "$(uname)" == "Linux" ]; then
        echo "Installing missing Linux system libraries for Chromium (requires sudo)..."
        python3 -m playwright install-deps chromium
    fi
    
    echo ""
    echo "Initial setup complete!"
else
    # FAST BOOT BYPASS
    source venv/bin/activate
fi

# =======================================================
# LAUNCH SEQUENCE
# =======================================================
mkdir -p "$HOME/.streamlit"
echo "[general]" > "$HOME/.streamlit/credentials.toml"
echo 'email = ""' >> "$HOME/.streamlit/credentials.toml"

clear
echo "======================================================="
echo " [ RUNNING ] SKIPPY IS OPENING IN YOUR BROWSER!"
echo ""
echo " *** DO NOT CLOSE THIS TERMINAL ***"
echo " Minimize it to keep Skippy running."
echo " When you are completely done, close this terminal"
echo " to turn the application off."
echo "======================================================="
echo ""

python3 -m streamlit run app.py --server.port=8501 --server.address=localhost --browser.gatherUsageStats=false