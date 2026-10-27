#!/bin/bash
set -e

# Ensure the script runs in the directory it is located in
cd "$(dirname "$0")"

echo "======================================================="
echo "        🦘 Skippy - AI Job CRM (Mac/Linux Launch)      "
echo "======================================================="
echo ""

# FAST BOOT: Check if the virtual environment is already built
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    echo "First-time setup detected. Setting up Skippy automatically..."
    echo ""

    # 1. Locate Python 3
    PYTHON_CMD=""
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        if python -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
            PYTHON_CMD="python"
        fi
    fi

    if [ -z "$PYTHON_CMD" ]; then
        echo "❌ [Error] Python 3 could not be found on your computer."
        echo ""
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "For Mac: Open Terminal and install Python via Homebrew:"
            echo "   brew install python"
        else
            echo "For Ubuntu/Debian/WSL: Open terminal and run:"
            echo "   sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
            echo "For Fedora:"
            echo "   sudo dnf install -y python3 python3-pip"
        fi
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo "⚙️  [1/3] Creating isolated Python environment..."
    rm -rf venv 2>/dev/null || true
    if ! $PYTHON_CMD -m venv venv 2>/dev/null; then
        # On Ubuntu/Debian, python3-venv may be missing
        if command -v apt-get &>/dev/null; then
            echo "Package python3-venv is required on your system."
            echo "Attempting to install python3-venv (may require sudo password)..."
            sudo apt update && sudo apt install -y python3-venv
            $PYTHON_CMD -m venv venv
        else
            echo "❌ Failed to create virtual environment."
            echo "Please ensure python3-venv is installed on your system."
            read -p "Press Enter to exit..."
            exit 1
        fi
    fi

    echo "📦 [2/3] Installing application dependencies..."
    ./venv/bin/python -m pip install --quiet --upgrade pip
    ./venv/bin/python -m pip install --quiet --default-timeout=120 --retries=5 -r requirements.txt

    echo "🌐 [3/3] Installing scraper browser driver (Chromium)..."
    ./venv/bin/python -m playwright install chromium

    if [ "$(uname)" = "Linux" ] && command -v apt-get &>/dev/null; then
        echo "Verifying Linux browser system libraries..."
        CHROME_BIN=$(find "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}" -name "chrome" -type f 2>/dev/null | head -n 1)
        if [ -z "$CHROME_BIN" ] || ldd "$CHROME_BIN" 2>/dev/null | grep -q "not found"; then
            ./venv/bin/python -m playwright install-deps chromium 2>/dev/null || true
        fi
    fi

    echo ""
    echo "🎉 Setup complete! Launching Skippy..."
    sleep 1
fi

# =======================================================
# LAUNCH SEQUENCE
# =======================================================
source venv/bin/activate

# Ensure template prompt files are initialized
if [ ! -s custom_prompt.txt ] && [ -f custom_prompt.template.txt ]; then
    cp custom_prompt.template.txt custom_prompt.txt 2>/dev/null || true
fi
if [ ! -s custom_user_prompt.txt ] && [ -f custom_prompt.template.txt ]; then
    cp custom_prompt.template.txt custom_user_prompt.txt 2>/dev/null || true
fi

# Suppress Streamlit email prompt cleanly
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export LITELLM_DISABLE_REDACT_SECRETS=true
export LITELLM_LOCAL_MODEL_COST_MAP=True
mkdir -p "$HOME/.streamlit" 2>/dev/null || true
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
    printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml" 2>/dev/null || true
fi

echo "======================================================="
echo " 🚀 SKIPPY IS OPENING IN YOUR BROWSER!"
echo ""
echo " 🌐 Dashboard: http://localhost:8501"
echo ""
echo " *** DO NOT CLOSE THIS WINDOW ***"
echo " Minimize this window to keep Skippy running."
echo " When you are finished, close this window to stop Skippy."
echo "======================================================="
echo ""

python -m streamlit run app.py --server.port=8501 --server.address=localhost --server.headless=false --browser.gatherUsageStats=false