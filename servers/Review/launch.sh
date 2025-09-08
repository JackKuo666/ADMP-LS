#!/bin/bash

# Review Service Startup Script

echo "🚀 Starting Review service..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set environment variables
export PYTHONPATH="$SCRIPT_DIR"

# Check Python environment
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not installed"
    exit 1
fi

# Check dependencies
if [ ! -f "requirement.txt" ]; then
    echo "⚠️ requirement.txt file not found"
    exit 1
fi

# Start service
echo "📡 Starting Review service on port 8880..."
python3 main.py