#!/bin/bash
cd "$(dirname "$0")"

echo "======================================================="
echo "             Skippy - Docker Bootstrapper"
echo "======================================================="
echo ""
echo "NOTE: You will need a valid AI API key (Gemini, OpenAI, GROK or Anthropic)"
echo "to use this application unless you are running a local Ollama model."
echo ""
echo "Building and starting the Skippy container..."
docker-compose up -d --build

echo ""
echo "Container is running! Opening your web browser..."

# Force the default browser to open based on the OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8501
else
    xdg-open http://localhost:8501
fi

# Terminal will now exit automatically