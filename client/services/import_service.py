import streamlit as st
import json
import uuid
from datetime import datetime
from typing import Dict, Any


def parse_json_chat(file_content: str) -> Dict[str, Any]:
    """
    Parse a JSON chat file and extract chat data
    """
    try:
        data = json.loads(file_content)
        return {
            'chat_id': str(uuid.uuid4()),  # Generate new ID for imported chat
            'chat_name': data.get('chat_name', 'Imported Chat'),
            'messages': data.get('messages', [])
        }
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON format: {str(e)}")
        return None


def import_chat_from_file(uploaded_file) -> Dict[str, Any]:
    """
    Import chat data from uploaded file (JSON format only)
    """
    if uploaded_file is None:
        return None
    
    file_content = uploaded_file.read().decode('utf-8')
    file_name = uploaded_file.name.lower()
    
    if file_name.endswith('.json'):
        return parse_json_chat(file_content)
    else:
        st.error("Unsupported file format. Please upload a .json file.")
        return None


def add_imported_chat_to_history(chat_data: Dict[str, Any]):
    """
    Add imported chat to session state history
    """
    if not chat_data or not chat_data.get('messages'):
        st.error("No valid chat data to import")
        return False
    
    # Add timestamp to chat name if it's a duplicate
    original_name = chat_data['chat_name']
    existing_names = [chat['chat_name'] for chat in st.session_state.get('history_chats', [])]
    
    if original_name in existing_names:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chat_data['chat_name'] = f"{original_name} (Imported {timestamp})"
    
    # Add to history
    st.session_state['history_chats'].append(chat_data)
    
    # Switch to the imported chat
    st.session_state['current_chat_index'] = 0
    st.session_state['current_chat_id'] = chat_data['chat_id']
    st.session_state['messages'] = chat_data['messages']
    
    return True


def create_import_widget():
    """
    Create a file upload widget for importing chat history (JSON format only)
    """
    st.markdown("**📁 Import Chat History:**")
    
    uploaded_file = st.file_uploader(
        "Choose a chat history file",
        type=['json'],
        help="Upload a previously exported chat history file (.json format only)"
    )
    
    if uploaded_file:
        if st.button("📥 Import Chat"):
            with st.spinner("Importing chat history..."):
                chat_data = import_chat_from_file(uploaded_file)
                if chat_data:
                    success = add_imported_chat_to_history(chat_data)
                    if success:
                        st.success(f"✅ Successfully imported chat: {chat_data['chat_name']}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to import chat")
                else:
                    st.error("❌ Invalid file format or content") 