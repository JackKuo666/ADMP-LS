import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Set environment variables
os.environ['PYTHONPATH'] = current_dir

from fastapi_mcp import FastApiMCP

# import logging
# If relative import fails, try absolute import
from app import app
# logger = get_logger(__name__)


# Create an MCP server based on this app
# mcp = FastApiMCP(app)

review_mcp = FastApiMCP(app, name="Review MCP", include_operations=["review_generate"],describe_full_response_schema=True,  # Describe the full response JSON-schema instead of just a response example
    describe_all_responses=True, )
check_mcp = FastApiMCP(app, name="Check MCP", include_operations=["health_check"],describe_full_response_schema=True,  # Describe the full response JSON-schema instead of just a response example
    describe_all_responses=True, )

# Mount the MCP server directly to your app
# mcp.mount_sse()
review_mcp.mount_sse(mount_path="/review")
check_mcp.mount_sse(mount_path="/check")

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    
    # Add current directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    print("🚀 Starting Review service...")
    print("📡 MCP Endpoints:")
    print("   - Review MCP: http://localhost:8880/review")
    print("   - Check MCP: http://localhost:8880/check")
    print("🌐 API Documentation: http://localhost:8880/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8880)
