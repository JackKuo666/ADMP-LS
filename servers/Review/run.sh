#!/bin/bash

# Review service startup script - simplest way

echo "🚀 Starting Review service..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Set environment variables
export PYTHONPATH="$SCRIPT_DIR"

echo "📁 Working directory: $SCRIPT_DIR"
echo "🐍 Python path: $PYTHONPATH"
echo "📡 Service endpoints:"
echo "   - Review MCP: http://localhost:8880/review"
echo "   - Check MCP: http://localhost:8880/check"
echo "🌐 API Documentation: http://localhost:8880/docs"
echo ""

# Start with main.py to include MCP mounts
python3 main.py