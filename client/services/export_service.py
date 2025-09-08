import streamlit as st
import json
from datetime import datetime
from typing import List, Dict, Any


def format_message_for_export(message: Dict[str, Any]) -> str:
    """
    Format a single message for export to Markdown
    """
    role = message.get("role", "unknown")
    content = message.get("content", "")
    tool = message.get("tool", "")
    
    formatted = f"## {role.title()}\n\n"
    
    if content:
        # Handle different content types
        if isinstance(content, str):
            # Check if this is a review report
            if "Literature Review Report" in content or "📚 Literature Review Report" in content:
                formatted += f"### 📚 Literature Review Report\n\n{content}\n\n"
                # Add download note for review reports
                formatted += "> **Note:** This review report can be downloaded as Markdown or PDF from the main interface.\n\n"
            else:
                formatted += f"{content}\n\n"
        else:
            formatted += f"```\n{content}\n```\n\n"
    
    if tool:
        formatted += f"### 🔧 Tool Message\n\n```yaml\n{tool}\n```\n\n"
    
    return formatted


def export_chat_to_markdown(chat_data: Dict[str, Any]) -> str:
    """
    Export a complete chat conversation to Markdown format
    """
    chat_id = chat_data.get("chat_id", "unknown")
    chat_name = chat_data.get("chat_name", "Unknown Chat")
    messages = chat_data.get("messages", [])
    
    # Count message types
    user_messages = sum(1 for msg in messages if msg.get("role") == "user")
    assistant_messages = sum(1 for msg in messages if msg.get("role") == "assistant")
    tool_messages = sum(1 for msg in messages if msg.get("tool"))
    review_reports = sum(1 for msg in messages if msg.get("role") == "assistant" and 
                        msg.get("content") and 
                        ("Literature Review Report" in str(msg.get("content")) or "📚 Literature Review Report" in str(msg.get("content"))))
    
    # Create markdown content
    markdown_content = f"# 💬 Chat: {chat_name}\n\n"
    markdown_content += f"**Chat ID:** `{chat_id}`\n"
    markdown_content += f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    markdown_content += f"**Total Messages:** {len(messages)}\n"
    markdown_content += f"**Message Breakdown:**\n"
    markdown_content += f"- 👤 User Messages: {user_messages}\n"
    markdown_content += f"- 🤖 Assistant Messages: {assistant_messages}\n"
    markdown_content += f"- 🔧 Tool Messages: {tool_messages}\n"
    markdown_content += f"- 📚 Review Reports: {review_reports}\n\n"
    markdown_content += "---\n\n"
    
    # Add each message
    for i, message in enumerate(messages, 1):
        role = message.get("role", "unknown")
        role_emoji = "👤" if role == "user" else "🤖" if role == "assistant" else "🔧"
        
        markdown_content += f"## {role_emoji} Message {i} ({role.title()})\n\n"
        markdown_content += format_message_for_export(message)
        markdown_content += "---\n\n"
    
    return markdown_content


def export_chat_to_json(chat_data: Dict[str, Any]) -> str:
    """
    Export a complete chat conversation to JSON format
    """
    chat_id = chat_data.get("chat_id")
    chat_name = chat_data.get("chat_name")
    messages = chat_data.get("messages", [])
    
    # 重新组织消息，确保ToolMessage正确保存
    processed_messages = []
    
    for i, message in enumerate(messages):
        processed_message = {
            "role": message.get("role"),
        }
        
        # 如果有content字段，添加到消息中
        if "content" in message and message["content"]:
            processed_message["content"] = message["content"]
        else:
            processed_message["content"] = ""
        
        # 如果有tool字段，添加到消息中
        if "tool" in message and message["tool"]:
            processed_message["tool"] = message["tool"]
        
        processed_messages.append(processed_message)
    
    export_data = {
        "chat_id": chat_id,
        "chat_name": chat_name,
        "export_date": datetime.now().isoformat(),
        "total_messages": len(processed_messages),
        "messages": processed_messages
    }
    
    return json.dumps(export_data, indent=2, ensure_ascii=False)


def get_chat_by_id(chat_id: str) -> Dict[str, Any]:
    """
    Get a specific chat by its ID from session state
    """
    # If it's the current chat, always build from live session messages to avoid staleness
    current_chat_id = st.session_state.get("current_chat_id")
    if current_chat_id == chat_id:
        current_messages = st.session_state.get("messages", [])
        # Prefer the name from history if available
        chat_name = st.session_state.get("current_chat_name", "Current Chat")
        for chat in st.session_state.get("history_chats", []):
            if chat.get("chat_id") == chat_id:
                chat_name = chat.get("chat_name", chat_name)
                break
        return {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "messages": current_messages
        }

    # Otherwise, return from history if present
    for chat in st.session_state.get("history_chats", []):
        if chat.get("chat_id") == chat_id:
            return chat
    
    return None


def create_download_button_for_chat(chat_id: str, file_format: str = "json"):
    """
    Create a download button for a specific chat
    """
    chat_data = get_chat_by_id(chat_id)
    if not chat_data:
        st.error("Chat not found")
        return
    
    if file_format == "json":
        content = export_chat_to_json(chat_data)
        filename = f"chat_{chat_data['chat_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        mime_type = "application/json"
    else:
        st.error("Unsupported file format")
        return
    
    st.download_button(
        label="📥 Download JSON",
        data=content,
        file_name=filename,
        mime=mime_type,
        help="Download complete chat history as JSON file"
    ) 