from typing import Dict, List
import streamlit as st

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from services.ai_service import create_llm_model
from services.logging_service import get_logger
from utils.async_helpers import run_async


async def setup_mcp_client(server_config: Dict[str, Dict]) -> MultiServerMCPClient:
    """Initialize a MultiServerMCPClient with the provided server configuration."""
    client = MultiServerMCPClient(server_config)
    return client

async def get_tools_from_client(client: MultiServerMCPClient) -> List[BaseTool]:
    """Get tools from the MCP client."""
    return await client.get_tools()

async def run_agent(agent, message: str) -> Dict:
    """Run the agent with the provided message."""
    return await agent.ainvoke({"messages": message})

async def run_tool(tool, **kwargs):
    """Run a tool with the provided parameters."""
    return await tool.ainvoke(**kwargs)

def connect_to_mcp_servers():
    logger = get_logger()
    
    # Clean up existing client if any
    client = st.session_state.get("client")
    if client:
        try:
            # No need to call __aexit__ since we're not using context manager
            logger.log_system_status("Cleaned up previous MCP client")
        except Exception as e:
            logger.log_error("MCP_Client_Cleanup_Error", str(e))
            st.warning(f"Error closing previous client: {str(e)}")

    # Collect LLM config dynamically from session state
    params = st.session_state['params']
    llm_provider = params.get("model_id")
    try:
        llm = create_llm_model(llm_provider, temperature=params['temperature'], max_tokens=params['max_tokens'])
        logger.log_system_status(f"Initialized LLM: {llm_provider}")
    except Exception as e:
        logger.log_error("LLM_Initialization_Error", str(e), {'provider': llm_provider})
        st.error(f"Failed to initialize LLM: {e}")
        st.stop()
        return
    
    # Setup new client
    try:
        st.session_state.client = run_async(setup_mcp_client(st.session_state.servers))
        st.session_state.tools = run_async(get_tools_from_client(st.session_state.client))
        st.session_state.agent = create_react_agent(llm, st.session_state.tools)
        
        # Log successful connection
        logger.log_system_status("MCP client setup completed", {
            'servers_count': len(st.session_state.servers),
            'tools_count': len(st.session_state.tools)
        })
        
        # 记录每个服务器的详细信息
        for server_name, server_config in st.session_state.servers.items():
            logger.log_mcp_connection(
                server_name, 
                server_config.get('url', 'unknown'), 
                True
            )
        
        # 记录所有可用工具
        tool_names = [tool.name for tool in st.session_state.tools]
        logger.log_system_status("Available MCP tools", {
            'tools': tool_names,
            'total_tools': len(tool_names)
        })
        
    except Exception as e:
        logger.log_error("MCP_Client_Setup_Error", str(e), {
            'servers': list(st.session_state.servers.keys()),
            'llm_provider': llm_provider
        })
        raise e
        

def disconnect_from_mcp_servers():
    # Clean up existing client if any and session state connections
    client = st.session_state.get("client")
    if client:
        try:
            # No need to call __aexit__ since we're not using context manager
            pass
        except Exception as e:
            st.warning(f"Error during disconnect: {str(e)}")
    else:
        st.info("No MCP connection to disconnect.")

    # Clean up session state
    st.session_state.client = None
    st.session_state.tools = []
    st.session_state.agent = None
