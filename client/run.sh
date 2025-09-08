#!/bin/bash
# 设置环境变量以确保日志输出到控制台
export PYTHONUNBUFFERED=1
export STREAMLIT_SERVER_PORT=8502
export STREAMLIT_SERVER_ADDRESS=0.0.0.0

echo "🚀 Starting MCP Playground with logging enabled..."
echo "📊 Logs will be displayed in this terminal"
echo "📁 Log files will be saved in logs/ directory"
echo ""

# 运行应用
streamlit run app.py --server.port=8502 --server.address=0.0.0.0