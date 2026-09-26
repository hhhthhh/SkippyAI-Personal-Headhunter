#!/bin/bash

# Ensure the script runs in the directory it's located in
cd "$(dirname "$0")"

echo "======================================================="
echo "             Skippy - Docker Bootstrapper"
echo "======================================================="
echo ""
echo "Building and starting the Skippy container..."
docker-compose up -d --build

echo ""
echo "======================================================="
echo " SUCCESS! Skippy is now running in the background."
echo ""
echo " Open your web browser and navigate to:"
echo " http://localhost:8501"
echo "======================================================="
echo ""