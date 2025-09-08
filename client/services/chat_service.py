import streamlit as st
from config import SERVER_CONFIG
import uuid
import json
import os
from services.logging_service import get_logger
from services.mcp_service import connect_to_mcp_servers

# Session state initialization
def init_session():
    defaults = {
        "params": {},
        "current_chat_id": None,
        "current_chat_index": 0,
        "history_chats": get_history(),
        "messages": [],
        "client": None,
        "agent": None,
        "tools": [],
        "tool_executions": [],
        "servers": SERVER_CONFIG['mcpServers'],
        "auto_connect_attempted": False
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def auto_connect_to_mcp():
    """Automatically connect to MCP servers on first page load"""
    try:
        logger = get_logger()
        logger.log_system_status("Auto-connecting to MCP servers on first load")
        
        # Check if params are configured before attempting connection
        params = st.session_state.get('params', {})
        if not params.get('model_id') or not params.get('temperature'):
            logger.log_system_status("Skipping auto-connect: LLM parameters not configured yet")
            st.session_state["auto_connect_attempted"] = True
            return
        
        # Attempt to connect to MCP servers
        connect_to_mcp_servers()
        
        # Mark auto-connect as attempted
        st.session_state["auto_connect_attempted"] = True
        
        # Log successful connection
        if st.session_state.get("agent"):
            logger.log_system_status("Successfully auto-connected to MCP servers", {
                'servers_count': len(st.session_state.servers),
                'tools_count': len(st.session_state.tools)
            })
        else:
            logger.log_system_status("Auto-connect attempted but no agent available")
            
    except Exception as e:
        # Log connection error but don't fail the app
        logger = get_logger()
        logger.log_error(
            "Auto_MCP_Connection_Error",
            str(e),
            {'servers': list(st.session_state.servers.keys())}
        )
        logger.log_system_status(f"Auto-connect failed: {str(e)}")
        
        # Mark as attempted even if failed
        st.session_state["auto_connect_attempted"] = True


def load_example_chats():
    """Load example chat histories from JSON files"""
    example_chats = []
    
    # Define example chat files
    example_files = [
        {
            "file": "chat_Bio_QA_mcp_agent_20250908_122027.json",
            "display_name": "Bio QA Example: What is DNA?"
        },
        {
            "file": "chat_Review_mcp_agent_20250908_121128.json", 
            "display_name": "Review Example: AML Risk Stratification"
        }
    ]
    
    # Get the directory of this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    chat_history_dir = os.path.join(current_dir, "..", "chat_history")
    
    for example in example_files:
        file_path = os.path.join(chat_history_dir, example["file"])
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                    # Update the chat name for display
                    chat_data['chat_name'] = example["display_name"]
                    example_chats.append(chat_data)
            except Exception as e:
                logger = get_logger()
                logger.log_error("LoadExampleChat", str(e), {"file": example["file"]})
    
    return example_chats


def get_history():
    if "history_chats" in st.session_state and st.session_state["history_chats"]:
        return st.session_state["history_chats"]
    else:
        # Load example chats first
        example_chats = load_example_chats()
        
        # Create a new chat
        chat_id = str(uuid.uuid4())
        new_chat = {'chat_id': chat_id,
                    'chat_name': 'New chat',
                    'messages': []}
        
        # Combine example chats with new chat
        all_chats = example_chats + [new_chat]
        
        st.session_state["current_chat_index"] = 0  # Select the new chat (after reversal in sidebar)
        st.session_state["current_chat_id"] = chat_id
        
        return all_chats

def get_current_chat(chat_id):
    """Get messages for the current chat."""
    for chat in st.session_state["history_chats"]:
        if chat['chat_id'] == chat_id:
            return chat['messages']
    return []

def _append_message_to_session(msg: dict) -> None:
    """
    Append *msg* to the current chat’s message list **and**
    keep history_chats in-sync.
    """
    chat_id = st.session_state["current_chat_id"]
    st.session_state["messages"].append(msg)
    for chat in st.session_state["history_chats"]:
        if chat["chat_id"] == chat_id:
            chat["messages"] = st.session_state["messages"]     # same list
            if chat["chat_name"] == "New chat":                 # rename once
                chat["chat_name"] = " ".join(msg["content"].split()[:5]) or "Empty"
            break

def create_chat():
    """Create a new chat session."""
    logger = get_logger()
    chat_id = str(uuid.uuid4())
    new_chat = {'chat_id': chat_id,
                'chat_name': 'New chat',
                'messages': []}
    
    st.session_state["history_chats"].append(new_chat)
    st.session_state["current_chat_index"] = 0
    st.session_state["current_chat_id"] = chat_id
    
    # Log chat creation
    logger.log_user_action("create_chat", {
        'chat_id': chat_id,
        'total_chats': len(st.session_state["history_chats"])
    })
    
    return new_chat

def delete_chat(chat_id: str):
    """Delete a chat from history."""
    if not chat_id: # protection against accidental call
        return

    logger = get_logger()
    
    # Log chat deletion
    chat_to_delete = None
    for chat in st.session_state["history_chats"]:
        if chat["chat_id"] == chat_id:
            chat_to_delete = chat
            break
    
    if chat_to_delete:
        logger.log_user_action("delete_chat", {
            'chat_id': chat_id,
            'chat_name': chat_to_delete.get('chat_name'),
            'messages_count': len(chat_to_delete.get('messages', []))
        })

    # 1) Remove from session_state.history_chats
    st.session_state["history_chats"] = [
        c for c in st.session_state["history_chats"]
        if c["chat_id"] != chat_id
    ]

    # 2) Switch current_chat to another one or create new
    if st.session_state["current_chat_id"] == chat_id:
        if st.session_state["history_chats"]:            # if chats still exist
            first = st.session_state["history_chats"][0]
            st.session_state["current_chat_id"] = first["chat_id"]
            st.session_state["current_chat_index"] = 0
            st.session_state["messages"] = first["messages"]
        else:                                            # if all deleted → new empty
            new_chat = create_chat()
            st.session_state["messages"] = new_chat["messages"]
    return