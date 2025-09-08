#!/bin/bash

# Retrieve service startup script - Biomedical RAG MCP service

echo "🚀 Starting Retrieve service (Biomedical RAG MCP)..."
echo "🔬 Service: Bio RAG MCP Server"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Set environment variables
export PYTHONPATH="$SCRIPT_DIR"
export PYTHONUNBUFFERED=1

echo "📁 Working directory: $SCRIPT_DIR"
echo "🐍 Python path: $PYTHONPATH"
echo "📡 Service endpoints:"
echo "   - Health check: http://localhost:9487/health"
echo "   - Document retrieval: POST http://localhost:9487/retrieve"
echo "   - Streaming chat (RAG): POST http://localhost:9487/stream-chat"
echo "   - Bio QA MCP SSE: http://127.0.0.1:9487/sse"
echo "🔧 Configuration: app_config_dev.yaml"
echo "📊 Logs: Check logs/ directory for detailed logs"
echo ""

# Check if .env file exists
if [ -f ".env" ]; then
    echo "✅ Environment file (.env) found"
else
    echo "⚠️  Warning: .env file not found, using system environment variables"
    echo "   Consider copying env_example.txt to .env and configuring it"
fi

echo "🌐 Starting server on port 9487..."
echo ""

# Start the service
python3 main.py
