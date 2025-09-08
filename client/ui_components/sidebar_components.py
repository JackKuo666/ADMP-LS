import streamlit as st
from config import MODEL_OPTIONS
import traceback
from services.mcp_service import connect_to_mcp_servers
from services.chat_service import create_chat, delete_chat, get_current_chat
from services.export_service import create_download_button_for_chat
from services.import_service import create_import_widget
from services.logging_service import get_logger
from utils.tool_schema_parser import extract_tool_parameters
from utils.async_helpers import reset_connection_state


def create_history_chat_container():
    history_container = st.sidebar.container(height=400, border=None)
    with history_container:
        chat_history_menu = [
                f"{chat['chat_name']}_::_{chat['chat_id']}"
                for chat in st.session_state["history_chats"]
            ]
        chat_history_menu = chat_history_menu[:50][::-1]
        
        if chat_history_menu:
            current_chat = st.radio(
                label="History Chats",
                format_func=lambda x: x.split("_::_")[0] + '...' if "_::_" in x else x,
                options=chat_history_menu,
                label_visibility="collapsed",
                index=st.session_state["current_chat_index"],
                key="current_chat"
            )
            
            if current_chat:
                new_chat_id = current_chat.split("_::_")[1]
                # Only update if chat actually changed
                if st.session_state.get('current_chat_id') != new_chat_id:
                    logger = get_logger()
                    logger.log_system_status(f"Switching from chat {st.session_state.get('current_chat_id')} to {new_chat_id}")
                    
                    st.session_state['current_chat_id'] = new_chat_id
                    # Update current chat index
                    for i, chat in enumerate(st.session_state["history_chats"]):
                        if chat['chat_id'] == new_chat_id:
                            st.session_state["current_chat_index"] = i
                            break
                    # Update messages to current chat
                    st.session_state["messages"] = get_current_chat(new_chat_id)
                    
                    logger.log_system_status(f"Loaded {len(st.session_state['messages'])} messages for chat {new_chat_id}")
                    # Debug: log message structure
                    for i, msg in enumerate(st.session_state["messages"]):
                        has_tool = "tool" in msg and msg["tool"]
                        has_content = "content" in msg and msg["content"]
                        logger.log_system_status(f"Message {i}: role={msg.get('role')}, has_tool={has_tool}, has_content={has_content}")
                
                # Add download buttons for the selected chat
                chat_id = current_chat.split("_::_")[1]
                st.markdown("---")
                st.markdown("**📥 Export Chat History:**")
                
                # Create download button for JSON export only
                create_download_button_for_chat(chat_id, "json")
                
                # Add import functionality
                st.markdown("---")
                create_import_widget()


def create_sidebar_chat_buttons():
    with st.sidebar:
        c1, c2 = st.columns(2)
        create_chat_button = c1.button(
            "New Chat", use_container_width=True, key="create_chat_button"
        )
        if create_chat_button:
            create_chat()
            st.rerun()

        delete_chat_button = c2.button(
            "Delete Chat", use_container_width=True, key="delete_chat_button"
        )
        if delete_chat_button and st.session_state.get('current_chat_id'):
            delete_chat(st.session_state['current_chat_id'])
            st.rerun()

def create_model_select_widget():
    params = st.session_state["params"]
    params['model_id'] = st.sidebar.selectbox('🔎 Choose model',
                               options=MODEL_OPTIONS.keys(),
                               index=0)
    
def create_provider_select_widget():
    params = st.session_state.setdefault('params', {})
    # Load previously selected provider or default to the first
    default_provider = params.get("model_id", list(MODEL_OPTIONS.keys())[0])
    default_index = list(MODEL_OPTIONS.keys()).index(default_provider)
    # Provider selector with synced state
    selected_provider = st.sidebar.selectbox(
        '🔎 Choose Provider',
        options=list(MODEL_OPTIONS.keys()),
        index=default_index,
        key="provider_selection",
        on_change=reset_connection_state
    )
    # Save new provider and its index
    if selected_provider:
        params['model_id'] = selected_provider
        params['provider_index'] = list(MODEL_OPTIONS.keys()).index(selected_provider)
        st.sidebar.success(f"Model: {MODEL_OPTIONS[selected_provider]}")

    # Dynamic input fields based on provider
    with st.sidebar.container():
        if selected_provider == "Bedrock":
            with st.expander("🔐 Bedrock Credentials", expanded=True):
                # Configuration mode selector
                config_mode = st.radio(
                    "Configuration Mode",
                    ["🔄 Default", "✏️ Custom"],
                    key="bedrock_config_mode",
                    horizontal=True
                )
                
                if config_mode == "🔄 Default":
                    # Use environment variables - Force update params to ensure using environment variables
                    from config import DEFAULT_ENV_CONFIG
                    env_config = DEFAULT_ENV_CONFIG.get('Bedrock', {})
                    
                    # Force set to environment variable values to ensure passing to LLM
                    params['region_name'] = env_config.get('region_name', '')
                    params['aws_access_key'] = env_config.get('aws_access_key', '')
                    params['aws_secret_key'] = env_config.get('aws_secret_key', '')
                    
                    st.info("🔒 Using configuration from environment variables")
                    if env_config.get('region_name'):
                        st.success(f"Region: {env_config.get('region_name')}")
                    else:
                        st.warning("⚠️ AWS_REGION environment variable not set")
                    if env_config.get('aws_access_key'):
                        st.success("✅ AWS Access Key configured")
                    else:
                        st.warning("⚠️ AWS_ACCESS_KEY_ID environment variable not set")
                    if env_config.get('aws_secret_key'):
                        st.success("✅ AWS Secret Key configured")
                    else:
                        st.warning("⚠️ AWS_SECRET_ACCESS_KEY environment variable not set")
                        
                else:  # Custom mode
                    # Clear parameters for user input
                    params['region_name'] = st.text_input("AWS Region", value='', placeholder="Enter AWS Region", key="region_name")
                    params['aws_access_key'] = st.text_input("AWS Access Key", value='', type="password", placeholder="Enter AWS Access Key", key="aws_access_key")
                    params['aws_secret_key'] = st.text_input("AWS Secret Key", value='', type="password", placeholder="Enter AWS Secret Key", key="aws_secret_key")
                
                # Test button (always show)
                if st.button("🧪 Test Connection", key="bedrock_test"):
                    from services.ai_service import test_llm_connection
                    test_params = {
                        'region_name': params.get('region_name'),
                        'aws_access_key': params.get('aws_access_key'),
                        'aws_secret_key': params.get('aws_secret_key')
                    }
                    success, message = test_llm_connection(selected_provider, test_params)
                    
                    # Log the test result
                    logger = get_logger()
                    logger.log_llm_test(selected_provider, success, None if success else message)
                    
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        else:
            with st.expander("🔐 API Key", expanded=True):
                # Configuration mode selector
                config_mode = st.radio(
                    "Configuration Mode",
                    ["🔄 Default", "✏️ Custom"],
                    key=f"{selected_provider.lower()}_config_mode",
                    horizontal=True
                )
                
                from config import DEFAULT_ENV_CONFIG
                env_config = DEFAULT_ENV_CONFIG.get(selected_provider, {})
                
                if config_mode == "🔄 Default":
                    # Use environment variables - Force update params to ensure using environment variables
                    # Force set to environment variable values to ensure passing to LLM
                    params['api_key'] = env_config.get('api_key', '')
                    params['base_url'] = env_config.get('base_url', '')
                    
                    st.info("🔒 Using configuration from environment variables")
                    if env_config.get('api_key'):
                        if selected_provider == "OpenAI":
                            st.success("✅ OpenAI API Key configured (hidden display)")
                        else:
                            st.success(f"✅ {selected_provider} API Key configured")
                    else:
                        st.warning(f"⚠️ {selected_provider.upper()}_API_KEY environment variable not set")
                    if env_config.get('base_url'):
                        st.success(f"Base URL: {env_config.get('base_url')}")
                    else:
                        st.info(f"Using default Base URL: {env_config.get('base_url', 'N/A')}")
                        
                else:  # Custom mode
                    # Clear parameters for user input
                    params['api_key'] = st.text_input(
                        f"{selected_provider} API Key", 
                        value='', 
                        type="password", 
                        placeholder=f"Enter {selected_provider} API Key",
                        key="api_key"
                    )
                    params['base_url'] = st.text_input(
                        f"{selected_provider} Base URL", 
                        value='',
                        placeholder=env_config.get('base_url', f"Enter {selected_provider} Base URL"),
                        key="base_url"
                    )
                
                # Test button (always show)
                if st.button("🧪 Test Connection", key=f"{selected_provider.lower()}_test"):
                    from services.ai_service import test_llm_connection
                    test_params = {
                        'api_key': params.get('api_key'),
                        'base_url': params.get('base_url')
                    }
                    success, message = test_llm_connection(selected_provider, test_params)
                    
                    # Log the test result
                    logger = get_logger()
                    logger.log_llm_test(selected_provider, success, None if success else message)
                    
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    

def create_advanced_configuration_widget():
    params = st.session_state["params"]
    with st.sidebar.expander("⚙️  Basic config", expanded=False):
        params['max_tokens'] = st.number_input("Max tokens",
                                    min_value=1024,
                                    max_value=10240,
                                    value=4096,
                                    step=512,)
        params['temperature'] = st.slider("Temperature", 0.0, 1.0, step=0.05, value=1.0)
                
def create_mcp_connection_widget():
    # Auto-connect to MCP servers after parameters are configured
    if not st.session_state.get("auto_connect_attempted", False):
        from services.chat_service import auto_connect_to_mcp
        auto_connect_to_mcp()
    
    with st.sidebar:
        st.subheader("Server Management")
        with st.expander(f"MCP Servers ({len(st.session_state.servers)})"):
            for name, config in st.session_state.servers.items():
                with st.container(border=True):
                    st.markdown(f"**Server:** {name}")
                    st.markdown(f"**URL:** {config['url']}")
                    if st.button(f"Remove {name}", key=f"remove_{name}"):
                        del st.session_state.servers[name]
                        st.rerun()

        if st.session_state.get("agent"):
            st.success(f"📶 Connected to {len(st.session_state.servers)} MCP servers!"
                       f" Found {len(st.session_state.tools)} tools.")
            if st.button("Disconnect to MCP Servers"):
                with st.spinner("Connecting to MCP servers..."):
                    try:
                        logger = get_logger()
                        logger.log_system_status("Disconnecting from MCP servers")
                        
                        reset_connection_state()
                        
                        # Log successful disconnection
                        logger.log_system_status("Successfully disconnected from MCP servers")
                        
                        st.rerun()
                    except Exception as e:
                        # Log disconnection error
                        logger.log_error(
                            "MCP_Disconnection_Error",
                            str(e),
                            {'servers': list(st.session_state.servers.keys())}
                        )
                        
                        st.error(f"Error disconnecting to MCP servers: {str(e)}")
                        st.code(traceback.format_exc(), language="python")
        else:
            st.warning("⚠️ Not connected to MCP server")
            if st.button("Connect to MCP Servers"):
                with st.spinner("Connecting to MCP servers..."):
                    try:
                        logger = get_logger()
                        logger.log_system_status("Attempting to connect to MCP servers")
                        
                        connect_to_mcp_servers()
                        
                        # Log successful connection
                        logger.log_system_status("Successfully connected to MCP servers", {
                            'servers_count': len(st.session_state.servers),
                            'tools_count': len(st.session_state.tools)
                        })
                        
                        st.rerun()
                    except Exception as e:
                        # Log connection error
                        logger.log_error(
                            "MCP_Connection_Error",
                            str(e),
                            {'servers': list(st.session_state.servers.keys())}
                        )
                        
                        st.error(f"Error connecting to MCP servers: {str(e)}")
                        st.code(traceback.format_exc(), language="python")

def create_mcp_tools_widget():
    with st.sidebar:
        if st.session_state.tools:
            st.subheader("🧰 Available Tools")

            selected_tool_name = st.selectbox(
                "Select a Tool",
                options=[tool.name for tool in st.session_state.tools],
                index=0
            )

            if selected_tool_name:
                selected_tool = next(
                    (tool for tool in st.session_state.tools if tool.name == selected_tool_name),
                    None
                )

                if selected_tool:
                    with st.container():
                        st.write("**Description:**")
                        st.write(selected_tool.description)

                        parameters = extract_tool_parameters(selected_tool)

                        if parameters:
                            st.write("**Parameters:**")
                            for param in parameters:
                                st.code(param)