#!/bin/bash
set -e

# Ensure the script runs in the directory it is located in
cd "$(dirname "$0")"

echo "======================================================="
echo "       🐳 Skippy - Docker One-Click Launch (Mac/Linux) "
echo "======================================================="
echo ""

# 1. Verify Docker is installed
if ! command -v docker &>/dev/null; then
    echo "❌ [Error] Docker is not installed on this system."
    echo ""
    echo "Please download and install Docker Desktop from:"
    echo "   https://www.docker.com/products/docker-desktop/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# 2. Check if Docker daemon is running
if ! docker info &>/dev/null; then
    echo "Docker Desktop is currently closed or starting up..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Attempting to launch Docker Desktop..."
        open -a Docker 2>/dev/null || true
        echo "Waiting for Docker to be ready..."
        for i in {1..30}; do
            if docker info &>/dev/null; then
                break
            fi
            sleep 2
        done
    fi

    if ! docker info &>/dev/null; then
        echo "❌ [Error] Could not connect to Docker."
        echo "Please start Docker Desktop, wait for it to finish starting, and run this script again."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# 3. Detect modern 'docker compose' vs legacy 'docker-compose'
DOCKER_COMPOSE=""
if docker compose version &>/dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "❌ [Error] Neither 'docker compose' nor 'docker-compose' was found."
    echo "Please update Docker Desktop to the latest version."
    read -p "Press Enter to exit..."
    exit 1
fi

# 4. Pre-create persistence files so Docker won't mount them as directories
if [ ! -s custom_prompt.txt ] && [ -f custom_prompt.template.txt ]; then
    cp custom_prompt.template.txt custom_prompt.txt 2>/dev/null || true
fi
if [ ! -s custom_user_prompt.txt ] && [ -f custom_prompt.template.txt ]; then
    cp custom_prompt.template.txt custom_user_prompt.txt 2>/dev/null || true
fi
touch skippy.db .env resume.md custom_prompt.txt custom_user_prompt.txt profile_alignment.json app_settings.json 2>/dev/null || true
if [ ! -s resumes.json ]; then
    echo "{}" > resumes.json 2>/dev/null || true
fi
if [ ! -s inbox.json ]; then
    echo "[]" > inbox.json 2>/dev/null || true
fi
if [ ! -s prompt_presets.json ]; then
    echo "{}" > prompt_presets.json 2>/dev/null || true
fi
if [ ! -s app_settings.json ]; then
    echo "{}" > app_settings.json 2>/dev/null || true
fi
chmod 600 skippy.db .env resume.md resumes.json inbox.json custom_prompt.txt custom_user_prompt.txt profile_alignment.json app_settings.json 2>/dev/null || true

echo "🚀 Building and starting the Skippy container..."
$DOCKER_COMPOSE up -d --build

echo ""
echo "⏳ Waiting for Skippy web server to become ready..."
for i in {1..20}; do
    if curl -s http://localhost:8501 &>/dev/null; then
        break
    fi
    sleep 1
done

echo ""
echo "======================================================="
echo " 🎉 SKIPPY IS RUNNING IN DOCKER!"
echo ""
echo " 🌐 Dashboard: http://localhost:8501"
echo ""
echo " To stop Skippy in the future, run: $DOCKER_COMPOSE down"
echo "======================================================="
echo ""

# Open web browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8501
else
    xdg-open http://localhost:8501 2>/dev/null || true
fi