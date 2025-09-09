import datetime
import streamlit as st
import base64
import uuid
import time
from langchain_core.messages import HumanMessage, ToolMessage
from services.ai_service import get_response_stream
from services.mcp_service import run_agent
from services.chat_service import get_current_chat, _append_message_to_session
from services.export_service import export_chat_to_markdown, export_chat_to_json
from services.logging_service import get_logger
from services.task_monitor import get_task_monitor
from utils.async_helpers import run_async
from utils.ai_prompts import make_system_prompt, make_main_prompt
import ui_components.sidebar_components as sd_compents
from  ui_components.main_components import display_tool_executions
from config import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
import traceback


def replace_citation(match, citation_to_doc, doc_id_to_info):
    """Replace citation markers with formatted citations"""
    citation_num = int(match.group(1))
    if citation_num in citation_to_doc:
        doc_id = citation_to_doc[citation_num]
        if doc_id in doc_id_to_info:
            doc_info = doc_id_to_info[doc_id]
            title = doc_info.get('title', 'N/A')
            return f"([{citation_num}]({doc_info.get('url', '#')} \"{title}\"))"
    return match.group(0)


def replace_footnote_citation(match, citation_to_doc, doc_id_to_info):
    """Replace footnote citation markers with formatted citations"""
    citation_num = int(match.group(1))
    if citation_num in citation_to_doc:
        doc_id = citation_to_doc[citation_num]
        if doc_id in doc_id_to_info:
            doc_info = doc_id_to_info[doc_id]
            title = doc_info.get('title', 'N/A')
            return f"([{citation_num}]({doc_info.get('url', '#')} \"{title}\"))"
    return match.group(0)


def replace_document_citation(match, citation_to_doc, doc_id_to_info):
    """Replace document citation markers with formatted citations"""
    citation_num = int(match.group(1))
    if citation_num in citation_to_doc:
        doc_id = citation_to_doc[citation_num]
        if doc_id in doc_id_to_info:
            doc_info = doc_id_to_info[doc_id]
            title = doc_info.get('title', 'N/A')
            return f"([{citation_num}]({doc_info.get('url', '#')} \"{title}\"))"
    return match.group(0)


def extract_bio_final_answer(raw: str) -> str | None:
    """
    Extract the final answer from bio_qa_stream_chat ToolMessage text marked with
    'Bio-QA-final-Answer：' (note the Chinese full-width colon).
    Compatible with two scenarios:
      A) SSE stream: Multiple lines containing 'data: {...}' JSON
      B) Plain text/code blocks: First appears ```bio-...``` code block, final answer appears at the end
    Returns plain text answer; returns None if not found.
    """
    if not raw:
        return None

    marker = "Bio-QA-final-Answer："

    # --- Scenario A: SSE line stream (contains 'data:')
    if "data:" in raw:
        final = []
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            # Parse JSON
            try:
                import json
                data = json.loads(line[6:])
            except Exception:
                continue
            if data.get("type") == "result":
                content = str(data.get("content", ""))
                if content.startswith(marker):
                    # Remove marker
                    final_text = content[len(marker):].strip()
                    final.append(final_text)
            elif data.get("type") == "done":
                # End flag, exit directly
                break
        if final:
            # Use the last occurrence (more stable)
            return final[-1].strip()

    # --- Scenario B: Plain text (does not contain 'data:'), directly find marker
    idx = raw.rfind(marker)
    if idx != -1:
        final_text = raw[idx + len(marker):].strip()
        # Remove possible code fence or extra backticks that might wrap it
        if final_text.startswith("```"):
            # Remove the first code fence
            final_text = final_text.lstrip("`")
        # Also simply remove trailing extra backticks
        final_text = final_text.rstrip("`").strip()
        return final_text or None

    return None


def extract_review_final_report(raw: str) -> str | None:
    """
    Extract the final report content from review_generate ToolMessage text marked with
    'Final_report\n'.
    Compatible with two scenarios:
      A) SSE stream: Multiple lines containing 'data: {...}' JSON
      B) Plain text: Directly find content after Final_report\n marker
    Returns plain text report; returns None if not found.
    """
    if not raw:
        return None

    marker = "Final_report\n"

    # --- Scenario A: SSE line stream (contains 'data:')
    if "data:" in raw:
        final_content = []
        found_marker = False
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            # Parse JSON
            try:
                import json
                data = json.loads(line[6:])
            except Exception:
                continue
            if data.get("type") == "result":
                content = str(data.get("content", ""))
                if content == marker:
                    found_marker = True
                    continue
                elif found_marker:
                    # Collect all content after marker
                    final_content.append(content)
            elif data.get("type") == "done":
                # End flag, exit directly
                break
        if final_content:
            return "".join(final_content).strip()

    # --- Scenario B: Plain text (does not contain 'data:'), directly find marker
    idx = raw.find(marker)
    if idx != -1:
        final_text = raw[idx + len(marker):].strip()
        # Remove possible code fence or extra backticks that might wrap it
        if final_text.startswith("```"):
            # Remove the first code fence
            final_text = final_text.lstrip("`")
        # Also simply remove trailing extra backticks
        final_text = final_text.rstrip("`").strip()
        return final_text or None

    return None


def create_download_button(content: str, filename: str, file_type: str = "md", tool_type: str = "literature_review"):
    """
    Create a download button that supports downloading as Markdown or PDF format
    
    Args:
        content: Content to download
        filename: Filename (without extension)
        file_type: File type, 'md' or 'pdf'
        tool_type: Tool type for appropriate filename generation
    """
    # Ensure a unique key per button instance to avoid duplicate element IDs
    counter = st.session_state.get("download_btn_counter", 0)
    st.session_state["download_btn_counter"] = counter + 1
    base_key = f"download_{tool_type}_{file_type}_{counter}"

    # Add timestamp to filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate appropriate filename based on tool type
    if tool_type == "bio_qa_stream_chat":
        base_filename = "bio_qa_report"
    elif tool_type == "review_generate":
        base_filename = "literature_review"
    else:
        base_filename = filename
    
    filename_with_timestamp = f"{base_filename}_{timestamp}"
    
    if file_type == "md":
        # Download as Markdown file
        st.download_button(
            label=f"📥 Download as Markdown",
            data=content,
            file_name=f"{filename_with_timestamp}.md",
            mime="text/markdown",
            help="Click to download report as Markdown format",
            key=f"{base_key}_md"
        )
    elif file_type == "pdf":
        try:
            # Use reportlab with markdown parsing (no system dependencies)
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
            from io import BytesIO
            import markdown
            
            # Convert markdown to HTML first for better parsing
            html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
            
            # Create PDF document
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=TA_LEFT
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                spaceBefore=20,
                alignment=TA_LEFT
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=6,
                alignment=TA_JUSTIFY
            )
            
            # Build PDF content
            story = []
            
            # Add title based on tool type
            if tool_type == "bio_qa_stream_chat":
                title = "Biological Q&A Report"
            elif tool_type == "review_generate":
                title = "Literature Review Report"
            else:
                title = "Report"
            
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 12))
            
            # Parse HTML content and convert to PDF elements
            from bs4 import BeautifulSoup, NavigableString
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            def element_text_with_links(element) -> str:
                parts = []
                for child in element.children:
                    if isinstance(child, NavigableString):
                        parts.append(str(child))
                    elif getattr(child, 'name', None) == 'a':
                        href = child.get('href', '#')
                        text = child.get_text(strip=True)
                        parts.append(f'<link href="{href}">{text}</link>')
                    else:
                        # Fallback to text for other inline elements
                        parts.append(child.get_text(strip=False))
                return ''.join(parts).strip()
            
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'code', 'pre', 'blockquote', 'ul', 'ol', 'li']):
                if element.name in ['h1', 'h2', 'h3']:
                    heading_text = element_text_with_links(element)
                    story.append(Paragraph(heading_text or element.get_text(), heading_style))
                    story.append(Spacer(1, 6))
                elif element.name == 'p':
                    text = element_text_with_links(element)
                    if text.strip():
                        story.append(Paragraph(text, body_style))
                elif element.name == 'code':
                    code_style = ParagraphStyle(
                        'CodeText',
                        parent=body_style,
                        fontName='Courier',
                        fontSize=10,
                        backColor='#f8f9fa'
                    )
                    story.append(Paragraph(element.get_text(), code_style))
                elif element.name == 'pre':
                    pre_style = ParagraphStyle(
                        'PreText',
                        parent=body_style,
                        fontName='Courier',
                        fontSize=10,
                        backColor='#f8f9fa',
                        leftIndent=20
                    )
                    story.append(Paragraph(element.get_text(), pre_style))
                    story.append(Spacer(1, 6))
                elif element.name == 'blockquote':
                    quote_style = ParagraphStyle(
                        'QuoteText',
                        parent=body_style,
                        leftIndent=20,
                        leftPadding=10,
                        borderWidth=1,
                        borderColor='#3498db',
                        borderPadding=5
                    )
                    quote_text = element_text_with_links(element)
                    story.append(Paragraph(quote_text or element.get_text(), quote_style))
                    story.append(Spacer(1, 6))
                elif element.name in ['ul', 'ol']:
                    index = 0
                    for li in element.find_all('li', recursive=False):
                        index += 1
                        li_text = element_text_with_links(li)
                        bullet = '• ' if element.name == 'ul' else f'{index}. '
                        story.append(Paragraph(f'{bullet}{li_text}', body_style))
                    story.append(Spacer(1, 6))
            
            # Generate PDF
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            # Create download button
            st.download_button(
                label="📥 Download as PDF",
                data=pdf_bytes,
                file_name=f"{filename_with_timestamp}.pdf",
                mime="application/pdf",
                help="Click to download report as PDF format",
                key=f"{base_key}_pdf"
            )
            
        except ImportError as e:
            st.warning(f"⚠️ Cannot generate PDF: Missing required libraries. Please install reportlab and beautifulsoup4. Error: {str(e)}")
        except Exception as e:
            st.error(f"❌ Error generating PDF: {str(e)}")


def main():
    # Initialize logger
    logger = get_logger()
    task_monitor = get_task_monitor()
    
    with st.sidebar:
        st.link_button("🚀 Parameter Extraction", "https://huggingface.co/spaces/jackkuo/Automated-Enzyme-Kinetics-Extractor", type="primary")
        st.subheader("Chat History")
    sd_compents.create_history_chat_container()

# ------------------------------------------------------------------ Chat Part
    # Main chat interface
    st.header("Chat with Agent")
    
    messages_container = st.container(border=True, height=600)
# ------------------------------------------------------------------ Chat history
     # Re-render previous messages
    if st.session_state.get('current_chat_id'):
        st.session_state["messages"] = get_current_chat(st.session_state['current_chat_id'])
        tool_count = 0
        
        # Debug: log message count
        logger.log_system_status(f"Re-rendering {len(st.session_state['messages'])} messages for chat {st.session_state['current_chat_id']}")
        
        # Load bio data for this chat if available
        chat_id = st.session_state['current_chat_id']
        bio_data_key = f"bio_data_{chat_id}"
        bio_data = st.session_state.get(bio_data_key, {})
        
        for m in st.session_state["messages"]:
            # Debug: log message structure
            has_tool = "tool" in m and m["tool"]
            has_content = "content" in m and m["content"]
            logger.log_system_status(f"Message: role={m.get('role')}, has_tool={has_tool}, has_content={has_content}")
            
            with messages_container.chat_message(m["role"]):
                # 先显示ToolMessage（如果有）
                if "tool" in m and m["tool"]:
                    tool_count += 1
                    # Display ToolMessage in collapsible format
                    with st.expander(f"🔧 ToolMessage - {tool_count}", expanded=False):
                        st.code(m["tool"], language='yaml')
                
                # 再显示content（如果有）
                if "content" in m and m["content"]:
                    content_text = str(m["content"])
                    
                    # Check if this is a bio final answer and restore citations
                    if (m["role"] == "assistant" and 
                        bio_data.get('has_bio_final_answer') and 
                        bio_data.get('bio_final_answer_content') == content_text):
                        
                        # Restore bio data for citation processing
                        bio_search_data = bio_data.get('bio_search_data', [])
                        bio_citation_data = bio_data.get('bio_citation_data', [])
                        web_search_data = bio_data.get('web_search_data', [])
                        
                        # Display found literature information
                        if bio_search_data or web_search_data:
                            total_bio_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in bio_search_data)
                            total_web_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in web_search_data)
                            if total_bio_docs > 0 and total_web_docs > 0:
                                st.markdown(f"### 📚 Analysis based on {total_bio_docs} scientific papers and {total_web_docs} web pages")
                            elif total_bio_docs > 0:
                                st.markdown(f"### 📚 Analysis based on {total_bio_docs} scientific papers")
                            else:
                                st.markdown(f"### 🌐 Analysis based on {total_web_docs} web pages")
                        
                        st.markdown("### 🎯 Final Answer")
                        
                        # Process citation markers in final answer
                        processed_answer = content_text
                        if bio_citation_data and (bio_search_data or web_search_data):
                            # Create docId to literature info mapping
                            doc_id_to_info = {}
                            # Add PubMed data
                            for search_data in bio_search_data:
                                bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                for doc in bio_docs:
                                    doc_id_to_info[doc.get('docId')] = doc
                            # Add web search data
                            for search_data in web_search_data:
                                web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                for doc in web_docs:
                                    doc_id_to_info[doc.get('docId')] = doc
                            
                            # Create citation number to docId mapping
                            citation_to_doc = {}
                            for citation in bio_citation_data:
                                citation_num = citation.get('citation')
                                doc_id = citation.get('docId')
                                citation_to_doc[citation_num] = doc_id
                            
                            # Replace citation markers
                            import re
                            
                            # First replace single citations
                            def replace_citation_local(match):
                                return replace_citation(match, citation_to_doc, doc_id_to_info)
                            processed_answer = re.sub(r'\[bio-rag-citation:(\d+)\]', replace_citation_local, processed_answer)
                            
                            def replace_footnote_citation_local(match):
                                return replace_footnote_citation(match, citation_to_doc, doc_id_to_info)
                            processed_answer = re.sub(r'\[\^(\d+)\]', replace_footnote_citation_local, processed_answer)
                            
                            def replace_document_citation_local(match):
                                return replace_document_citation(match, citation_to_doc, doc_id_to_info)
                            processed_answer = re.sub(r'\[document (\d+)\]', replace_document_citation_local, processed_answer)
                            
                            # Remove bottom references section (since we display complete reference list below)
                            processed_answer = re.sub(r'\n\nReferences:.*$', '', processed_answer, flags=re.DOTALL)
                            
                            # Then process consecutive citations, add separators
                            processed_answer = re.sub(r'\](\[)', r'], \1', processed_answer)
                        
                        st.markdown(processed_answer)
                        
                        # Display citation information
                        if bio_citation_data:
                            st.markdown(f"### 📖 References ({len(bio_citation_data)} citations)")
                            
                            # Create docId to literature info mapping
                            doc_id_to_info = {}
                            # Add PubMed data
                            for search_data in bio_search_data:
                                bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                for doc in bio_docs:
                                    doc_id_to_info[doc.get('docId')] = doc
                            # Add web search data
                            for search_data in web_search_data:
                                web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                for doc in web_docs:
                                    doc_id_to_info[doc.get('docId')] = doc
                            
                            # Display citation list
                            for citation in bio_citation_data:
                                doc_id = citation.get('docId')
                                citation_num = citation.get('citation')
                                source = citation.get('source', '')
                                
                                if doc_id in doc_id_to_info:
                                    doc_info = doc_id_to_info[doc_id]
                                    title = doc_info.get('title', 'N/A')
                                    url = doc_info.get('url', '#')
                                    
                                    if source == 'webSearch':
                                        st.markdown(f"[{citation_num}] {title}. [Link]({url})")
                                    else:
                                        author = doc_info.get('author', 'N/A')
                                        journal = doc_info.get('JournalInfo', 'N/A')
                                        
                                        authors = author.split(', ')
                                        if len(authors) > 3:
                                            display_author = ', '.join(authors[:3]) + ' et al.'
                                        else:
                                            display_author = author
                                        
                                        st.markdown(f"[{citation_num}] {display_author}. {title}. {journal}. [Link]({url})")
                                else:
                                    st.markdown(f"[{citation_num}] Document ID: {doc_id}")
                    else:
                        # Normal content display
                        st.markdown(content_text)
                    
                    # Check if this is a review report and add download buttons
                    if m["role"] == "assistant" and m["content"]:
                        # Try to detect if this is a literature review report
                        content_text = str(m["content"])
                        if ("Literature Review Report" in content_text or 
                            "📚 Literature Review Report" in content_text or
                            len(content_text) > 500):  # Assume long content might be a review report
                            # Add download buttons for review reports
                            st.markdown("---")
                            st.markdown("### 📥 Download Options")
                            col1, col2 = st.columns(2)
                            with col1:
                                create_download_button(content_text, "literature_review", "md", "bio_qa_stream_chat")
                            with col2:
                                create_download_button(content_text, "literature_review", "pdf", "bio_qa_stream_chat")

# ------------------------------------------------------------------ Chat input
    user_text = st.chat_input("Ask a question or explore available MCP tools")

# ------------------------------------------------------------------ SideBar widgets
    # Main sidebar widgets
    sd_compents.create_sidebar_chat_buttons()
    sd_compents.create_provider_select_widget()
    sd_compents.create_advanced_configuration_widget()
    sd_compents.create_mcp_connection_widget()
    sd_compents.create_mcp_tools_widget()

# ------------------------------------------------------------------ Main Logic
    if user_text is None:  # nothing submitted yet
        st.stop()
    
    params = st.session_state.get('params')
    if not (
        params.get('api_key') or
        (   params.get('model_id') == 'Bedrock' and
            params.get('region_name') and
            params.get('aws_access_key') and
            params.get('aws_secret_key')
        )
    ):
        err_mesg = "❌ Missing credentials: provide either an API key or complete AWS credentials."
        _append_message_to_session({"role": "assistant", "content": err_mesg})
        with messages_container.chat_message("assistant"):
            st.markdown(err_mesg)
        st.rerun()

# ------------------------------------------------------------------ handle question (if any text)
    if user_text:
        # Log user message
        logger.log_chat_message("user", user_text, st.session_state.get('current_chat_id'))
        
        user_text_dct = {"role": "user", "content": user_text}
        _append_message_to_session(user_text_dct)
        with messages_container.chat_message("user"):
            st.markdown(user_text)

        with st.spinner("Thinking…", show_time=True):
            # Start monitoring long-running task
            task_id = str(uuid.uuid4())
            task_monitor.start_monitoring(
                task_id, 
                f"MCP_Agent_Response_{st.session_state.get('current_chat_id', 'unknown')}",
                st.session_state.get('current_chat_id')
            )
            
            start_time = time.time()
            system_prompt = make_system_prompt()
            main_prompt = make_main_prompt(user_text)
            try:
                # If agent is available, use it
                if st.session_state.agent:
                    logger.log_system_status("Using MCP agent for response")
                    
                    # 记录可用的MCP工具
                    available_tools = [tool.name for tool in st.session_state.tools]
                    logger.log_mcp_agent_usage("ReactAgent", available_tools, st.session_state.get('current_chat_id'))
                    
                    response = run_async(run_agent(st.session_state.agent, user_text))
                    tool_output = None
                    tools_used_in_response = []
                    
                    # Extract tool executions if available
                    if "messages" in response:
                        logger.log_system_status(f"Processing {len(response['messages'])} messages from agent response")
                        for msg in response["messages"]:
                            # Debug: log message type
                            msg_type = type(msg).__name__
                            logger.log_system_status(f"Processing message type: {msg_type}")
                            
                            # Look for AIMessage with tool calls
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                logger.log_system_status(f"Found tool calls: {msg.tool_calls}")
                                for tool_call in msg.tool_calls:
                                    tools_used_in_response.append(tool_call['name'])
                                    
                                    # Log tool call
                                    logger.log_mcp_tool_call(
                                        tool_call['name'],
                                        tool_call['args'],
                                        st.session_state.get('current_chat_id')
                                    )
                                    
                                    # Find corresponding ToolMessage
                                    tool_output = next(
                                        (m.content for m in response["messages"] 
                                            if isinstance(m, ToolMessage) and 
                                            m.tool_call_id == tool_call['id']),
                                        None
                                    )
                                    if tool_output:
                                        # Log tool response
                                        logger.log_mcp_tool_response(
                                            tool_call['name'],
                                            tool_output,
                                            st.session_state.get('current_chat_id')
                                        )
                                        
                                        st.session_state.tool_executions.append({
                                            "tool_name": tool_call['name'],
                                            "input": tool_call['args'],
                                            "output": tool_output,
                                            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                        })
                            elif hasattr(msg, 'name') and msg.name:
                                logger.log_system_status(f"Found ToolMessage: {msg.name}")
                            else:
                                logger.log_system_status(f"Message has no tool calls or name: {msg}")
                    
                    # 记录实际使用的工具
                    if tools_used_in_response:
                        logger.log_mcp_agent_usage("Response", tools_used_in_response, st.session_state.get('current_chat_id'))
                    else:
                        logger.log_system_status("No MCP tools used in this response")
                    # Extract and display the response
                    output = ""
                    tool_count = 0
                    # Initialize bio QA data from session state or create new
                    chat_id = st.session_state.get('current_chat_id')
                    bio_data_key = f"bio_data_{chat_id}" if chat_id else "bio_data_default"
                    
                    if bio_data_key not in st.session_state:
                        st.session_state[bio_data_key] = {
                            'bio_final_answer_content': "",
                            'has_bio_final_answer': False,
                            'review_final_report_content': "",
                            'has_review_final_report': False,
                            'bio_search_data': [],
                            'bio_citation_data': [],
                            'web_search_data': []
                        }
                    
                    # Load existing data or initialize new
                    bio_data = st.session_state[bio_data_key]
                    bio_final_answer_content = bio_data['bio_final_answer_content']
                    has_bio_final_answer = bio_data['has_bio_final_answer']
                    review_final_report_content = bio_data['review_final_report_content']
                    has_review_final_report = bio_data['has_review_final_report']
                    bio_search_data = bio_data['bio_search_data']
                    bio_citation_data = bio_data['bio_citation_data']
                    web_search_data = bio_data['web_search_data']
                    
                    if "messages" in response:
                        for msg in response["messages"]:
                            if isinstance(msg, HumanMessage):
                                continue  # Skip human messages
                            elif hasattr(msg, 'name') and msg.name:  # ToolMessage
                                tool_count += 1
                                with messages_container.chat_message("assistant"):
                                    # Parse SSE stream data if it's a streaming tool response
                                    if (msg.name == "bio_qa_stream_chat" or msg.name == "review_generate" or msg.name == "health_check") and "data:" in msg.content:
                                        if msg.name == "bio_qa_stream_chat":
                                            st.write("**🔬 Biological Q&A Results:**")
                                        elif msg.name == "review_generate":
                                            st.write("**📚 Literature Review Generation:**")
                                        elif msg.name == "health_check":
                                            st.write("**🏥 Health Check Results:**")
                                        
                                        # Parse and display streaming content
                                        lines = msg.content.split('\n')
                                        handled_final_answer = False
                                        handled_final_report = False
                                        final_report_content = []
                                        for line in lines:
                                            if line.startswith('data: '):
                                                try:
                                                    import json
                                                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                                                    if data.get('type') == 'result':
                                                        content = data.get('content', '')
                                                        # Check if this is a final answer
                                                        if content.startswith("Bio-QA-final-Answer：") and not handled_final_answer:
                                                            # Extract final answer content
                                                            bio_final_answer_content = content.replace("Bio-QA-final-Answer：", "").strip()
                                                            # Save to session state
                                                            bio_data['bio_final_answer_content'] = bio_final_answer_content
                                                            bio_data['has_bio_final_answer'] = True
                                                            st.session_state[bio_data_key] = bio_data
                                                            
                                                            # Set as main output
                                                            output = bio_final_answer_content
                                                            # Set flag to skip LLM processing
                                                            has_bio_final_answer = True
                                                            # Display final answer immediately in main conversation area
                                                            st.markdown("---")
                                                            # Display found literature information
                                                            if bio_search_data or web_search_data:
                                                                total_bio_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in bio_search_data)
                                                                total_web_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in web_search_data)
                                                                # total_docs = total_bio_docs + total_web_docs
                                                                if total_bio_docs > 0 and total_web_docs > 0:
                                                                    st.markdown(f"### 📚 Analysis based on {total_bio_docs} scientific papers and {total_web_docs} web pages")
                                                                elif total_bio_docs > 0:
                                                                    st.markdown(f"### 📚 Analysis based on {total_bio_docs} scientific papers")
                                                                else:
                                                                    st.markdown(f"### 🌐 Analysis based on {total_web_docs} web pages")
                                                            

                                                            
                                                            st.markdown("### 🎯 Final Answer")
                                                            
                                                            # Process citation markers in final answer
                                                            processed_answer = bio_final_answer_content
                                                            if bio_citation_data and (bio_search_data or web_search_data):
                                                                # Create docId to literature info mapping
                                                                doc_id_to_info = {}
                                                                # Add PubMed data
                                                                for search_data in bio_search_data:
                                                                    bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                                    for doc in bio_docs:
                                                                        doc_id_to_info[doc.get('docId')] = doc
                                                                # Add web search data
                                                                for search_data in web_search_data:
                                                                    web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                                    for doc in web_docs:
                                                                        doc_id_to_info[doc.get('docId')] = doc
                                                                
                                                                # Create citation number to docId mapping
                                                                citation_to_doc = {}
                                                                for citation in bio_citation_data:
                                                                    citation_num = citation.get('citation')
                                                                    doc_id = citation.get('docId')
                                                                    citation_to_doc[citation_num] = doc_id
                                                                
                                                                # Replace citation markers
                                                                import re
                                                                # First replace single citations
                                                                processed_answer = re.sub(r'\[bio-rag-citation:(\d+)\]', replace_citation, processed_answer)
                                                                
                                                                processed_answer = re.sub(r'\[\^(\d+)\]', replace_footnote_citation, processed_answer)
                                                                
                                                                processed_answer = re.sub(r'\[document (\d+)\]', replace_document_citation, processed_answer)
                                                                
                                                                # Remove bottom references section (since we display complete reference list below)
                                                                processed_answer = re.sub(r'\n\nReferences:.*$', '', processed_answer, flags=re.DOTALL)
                                                                
                                                                # Then process consecutive citations, add separators
                                                                processed_answer = re.sub(r'\](\[)', r'], \1', processed_answer)
                                                            
                                                            st.markdown(processed_answer)
                                                            
                                                            # Display citation information (moved below final answer)
                                                            if bio_citation_data:
                                                                st.markdown(f"### 📖 References ({len(bio_citation_data)} citations)")
                                                                
                                                                # Create docId to literature info mapping
                                                                doc_id_to_info = {}
                                                                # Add PubMed data
                                                                for search_data in bio_search_data:
                                                                    bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                                    for doc in bio_docs:
                                                                        doc_id_to_info[doc.get('docId')] = doc
                                                                # Add web search data
                                                                for search_data in web_search_data:
                                                                    web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                                    for doc in web_docs:
                                                                        doc_id_to_info[doc.get('docId')] = doc
                                                                
                                                                # Display citation list, associate with literature info (standard reference format)
                                                                for citation in bio_citation_data:
                                                                    doc_id = citation.get('docId')
                                                                    citation_num = citation.get('citation')
                                                                    source = citation.get('source', '')
                                                                    
                                                                    if doc_id in doc_id_to_info:
                                                                        doc_info = doc_id_to_info[doc_id]
                                                                        title = doc_info.get('title', 'N/A')
                                                                        url = doc_info.get('url', '#')
                                                                        
                                                                        if source == 'webSearch':
                                                                            # Web citation format: [number] title. [link](URL)
                                                                            st.markdown(f"[{citation_num}] {title}. [Link]({url})")
                                                                        else:
                                                                            # PubMed literature citation format: [number] author. title. journal info. [link](URL)
                                                                            author = doc_info.get('author', 'N/A')
                                                                            journal = doc_info.get('JournalInfo', 'N/A')
                                                                            
                                                                            # Process author info, only show first 3
                                                                            authors = author.split(', ')
                                                                            if len(authors) > 3:
                                                                                display_author = ', '.join(authors[:3]) + ' et al.'
                                                                            else:
                                                                                display_author = author
                                                                            
                                                                            st.markdown(f"[{citation_num}] {display_author}. {title}. {journal}. [Link]({url})")
                                                                    else:
                                                                        st.markdown(f"[{citation_num}] Document ID: {doc_id}")
                                                            
                                                            # Build complete content for download (including references)
                                                            complete_content = ""
                                                            
                                                            # Add analysis information
                                                            if bio_search_data or web_search_data:
                                                                total_bio_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in bio_search_data)
                                                                total_web_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in web_search_data)
                                                                if total_bio_docs > 0 and total_web_docs > 0:
                                                                    complete_content += f"### 📚 Analysis based on {total_bio_docs} scientific papers and {total_web_docs} web pages\n\n"
                                                                elif total_bio_docs > 0:
                                                                    complete_content += f"### 📚 Analysis based on {total_bio_docs} scientific papers\n\n"
                                                                else:
                                                                    complete_content += f"### 🌐 Analysis based on {total_web_docs} web pages\n\n"
                                                            
                                                            # Add final answer
                                                            complete_content += "### 🎯 Final Answer\n\n"
                                                            complete_content += processed_answer + "\n\n"
                                                            
                                                            # Add references
                                                            if bio_citation_data:
                                                                complete_content += f"### 📖 References ({len(bio_citation_data)} citations)\n\n"
                                                                
                                                                # Create docId to literature info mapping
                                                                doc_id_to_info = {}
                                                                # Add PubMed data
                                                                for search_data in bio_search_data:
                                                                    bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                                    for doc in bio_docs:
                                                                        doc_id_to_info[doc.get('docId')] = doc
                                                                # Add web search data
                                                                for search_data in web_search_data:
                                                                    web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                                    for doc in web_docs:
                                                                        doc_id_to_info[doc.get('docId')] = doc
                                                                
                                                                # Add citation list to complete content
                                                                for citation in bio_citation_data:
                                                                    doc_id = citation.get('docId')
                                                                    citation_num = citation.get('citation')
                                                                    source = citation.get('source', '')
                                                                    
                                                                    if doc_id in doc_id_to_info:
                                                                        doc_info = doc_id_to_info[doc_id]
                                                                        title = doc_info.get('title', 'N/A')
                                                                        url = doc_info.get('url', '#')
                                                                        
                                                                        if source == 'webSearch':
                                                                            complete_content += f"[{citation_num}] {title}. [Link]({url})\n\n"
                                                                        else:
                                                                            author = doc_info.get('author', 'N/A')
                                                                            journal = doc_info.get('JournalInfo', 'N/A')
                                                                            
                                                                            authors = author.split(', ')
                                                                            if len(authors) > 3:
                                                                                display_author = ', '.join(authors[:3]) + ' et al.'
                                                                            else:
                                                                                display_author = author
                                                                            
                                                                            complete_content += f"[{citation_num}] {display_author}. {title}. {journal}. [Link]({url})\n\n"
                                                                    else:
                                                                        complete_content += f"[{citation_num}] Document ID: {doc_id}\n\n"
                                                            
                                                            # Add download buttons for Bio QA final answer (with complete content)
                                                            st.markdown("---")
                                                            st.markdown("### 📥 Download Options")
                                                            col1, col2 = st.columns(2)
                                                            with col1:
                                                                create_download_button(complete_content, "bio_qa_report", "md", "bio_qa_stream_chat")
                                                            with col2:
                                                                create_download_button(complete_content, "bio_qa_report", "pdf", "bio_qa_stream_chat")
                                                            
                                                            # Save complete content to session history
                                                            _append_message_to_session({'role': 'assistant', 'content': complete_content})
                                                            
                                                            # Force immediate rerender so Download Options appear without needing a new interaction
                                                            st.rerun()

                                                            handled_final_answer = True
                                                        # Check if this is a final report marker
                                                        elif content == "Final_report\n" and not handled_final_report:
                                                            handled_final_report = True
                                                            # Start collecting final report content
                                                            continue
                                                        elif handled_final_report:
                                                            # Collect final report content
                                                            final_report_content.append(content)
                                                        else:
                                                            # Try to parse JSON data and store
                                                            try:
                                                                import json
                                                                json_data = json.loads(content)
                                                                if json_data.get("type") == "search" and json_data.get("handler") == "QASearch":
                                                                    handler_param = json_data.get('handlerParam', {})
                                                                    source = handler_param.get('source', '')
                                                                    if source == 'pubmed':
                                                                        bio_search_data.append(json_data)
                                                                        # Save to session state
                                                                        bio_data['bio_search_data'] = bio_search_data
                                                                        st.session_state[bio_data_key] = bio_data
                                                                        st.write(f"🔍 Found {len(handler_param.get('bioDocs', []))} relevant papers")
                                                                    elif source == 'webSearch':
                                                                        web_search_data.append(json_data)
                                                                        # Save to session state
                                                                        bio_data['web_search_data'] = web_search_data
                                                                        st.session_state[bio_data_key] = bio_data
                                                                        st.write(f"🌐 Found {len(handler_param.get('bioDocs', []))} relevant web pages")
                                                                elif isinstance(json_data, list) and len(json_data) > 0 and "source" in json_data[0] and "citation" in json_data[0]:
                                                                    # This is citation data
                                                                    bio_citation_data.extend(json_data)
                                                                    # Save to session state
                                                                    bio_data['bio_citation_data'] = bio_citation_data
                                                                    st.session_state[bio_data_key] = bio_data
                                                                    st.write(f"📝 Generated citation information, {len(json_data)} citations total")
                                                                else:
                                                                    st.write(content)
                                                            except json.JSONDecodeError:
                                                                # If not JSON, display content normally
                                                                st.write(content)
                                                    elif data.get('type') == 'done':
                                                        st.success("✅ Answer completed")
                                                except json.JSONDecodeError:
                                                    continue
                                        
                                        # Process collected final report content
                                        if handled_final_report and final_report_content:
                                            review_final_report_content = "".join(final_report_content).strip()
                                            
                                            # Always display ToolMessage (collapsible)
                                            with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                st.code(msg.content, language='yaml')
                                            
                                            # Display final report in main conversation area
                                            with messages_container.chat_message("assistant"):
                                                st.markdown("---")
                                                st.markdown("### 📚 Literature Review Report")
                                                st.markdown(review_final_report_content)
                                                
                                                # Add download buttons to main conversation area (persistent)
                                                st.markdown("---")
                                                st.markdown("### 📥 Download Options")
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    create_download_button(review_final_report_content, "literature_review", "md", "review_generate")
                                                with col2:
                                                    create_download_button(review_final_report_content, "literature_review", "pdf", "review_generate")
                                            
                                            # Set flags and output
                                            has_review_final_report = True
                                            output = review_final_report_content
                                            
                                            # Save final report to session history with download buttons info
                                            _append_message_to_session({'role': 'assistant', 'content': review_final_report_content})
                                            # Also save the original ToolMessage for reference
                                            _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                                            
                                            # Force immediate rerender so Download Options appear without needing a new interaction
                                            st.rerun()
                                        else:
                                            # Save tool message to session history
                                            with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                st.code(msg.content, language='yaml')
                                            _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                                    else:
                                        # For non-streaming or non-SSE returned tool messages, prioritize parsing bio_qa_stream_chat final answer
                                        if msg.name == "bio_qa_stream_chat":
                                            # Try to extract search data
                                            try:
                                                import json
                                                import re
                                                # Find JSON data blocks
                                                json_matches = re.findall(r'```bio-chat-agent-task\n(.*?)\n```', msg.content, re.DOTALL)
                                                for json_str in json_matches:
                                                    try:
                                                        json_data = json.loads(json_str)
                                                        if json_data.get("type") == "search" and json_data.get("handler") == "QASearch":
                                                            handler_param = json_data.get('handlerParam', {})
                                                            source = handler_param.get('source', '')
                                                            if source == 'pubmed':
                                                                bio_search_data.append(json_data)
                                                                # Save to session state
                                                                bio_data['bio_search_data'] = bio_search_data
                                                                st.session_state[bio_data_key] = bio_data
                                                            elif source == 'webSearch':
                                                                web_search_data.append(json_data)
                                                                # Save to session state
                                                                bio_data['web_search_data'] = web_search_data
                                                                st.session_state[bio_data_key] = bio_data
                                                    except json.JSONDecodeError:
                                                        continue
                                                
                                                # Find citation data blocks
                                                citation_matches = re.findall(r'```bio-resource-lookup\n(.*?)\n```', msg.content, re.DOTALL)
                                                for citation_str in citation_matches:
                                                    try:
                                                        citation_data = json.loads(citation_str)
                                                        if isinstance(citation_data, list) and len(citation_data) > 0 and "source" in citation_data[0] and "citation" in citation_data[0]:
                                                            bio_citation_data.extend(citation_data)
                                                            # Save to session state
                                                            bio_data['bio_citation_data'] = bio_citation_data
                                                            st.session_state[bio_data_key] = bio_data
                                                    except json.JSONDecodeError:
                                                        continue
                                            except Exception:
                                                pass
                                            
                                            extracted = extract_bio_final_answer(msg.content)
                                            if extracted:
                                                # Always display ToolMessage (collapsible)
                                                with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                    st.code(msg.content, language='yaml')
                                                
                                                # Then display final answer in main conversation area
                                                with messages_container.chat_message("assistant"):
                                                    # Display found literature information
                                                    if bio_search_data or web_search_data:
                                                        total_bio_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in bio_search_data)
                                                        total_web_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in web_search_data)
                                                        total_docs = total_bio_docs + total_web_docs
                                                        if total_bio_docs > 0 and total_web_docs > 0:
                                                            st.markdown(f"### 📚 Analysis based on {total_bio_docs} scientific papers and {total_web_docs} web pages")
                                                        elif total_bio_docs > 0:
                                                            st.markdown(f"### 📚 Analysis based on {total_bio_docs} scientific papers")
                                                        else:
                                                            st.markdown(f"### 🌐 Analysis based on {total_web_docs} web pages")
                                                    

                                                    
                                                    st.markdown("### 🎯 Final Answer")
                                                    
                                                    # Process citation markers in final answer
                                                    processed_answer = extracted
                                                    if bio_citation_data and (bio_search_data or web_search_data):
                                                        # Create docId to literature info mapping
                                                        doc_id_to_info = {}
                                                        # Add PubMed data
                                                        for search_data in bio_search_data:
                                                            bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                            for doc in bio_docs:
                                                                doc_id_to_info[doc.get('docId')] = doc
                                                        # Add web search data
                                                        for search_data in web_search_data:
                                                            web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                            for doc in web_docs:
                                                                doc_id_to_info[doc.get('docId')] = doc
                                                        
                                                        # Create citation number to docId mapping
                                                        citation_to_doc = {}
                                                        for citation in bio_citation_data:
                                                            citation_num = citation.get('citation')
                                                            doc_id = citation.get('docId')
                                                            citation_to_doc[citation_num] = doc_id
                                                        
                                                        # Replace citation markers
                                                        import re
                                                        # First replace single citations
                                                        def replace_citation_local2(match):
                                                            return replace_citation(match, citation_to_doc, doc_id_to_info)
                                                        processed_answer = re.sub(r'\[bio-rag-citation:(\d+)\]', replace_citation_local2, processed_answer)
                                                        
                                                        def replace_footnote_citation_local2(match):
                                                            return replace_footnote_citation(match, citation_to_doc, doc_id_to_info)
                                                        processed_answer = re.sub(r'\[\^(\d+)\]', replace_footnote_citation_local2, processed_answer)
                                                        
                                                        def replace_document_citation_local2(match):
                                                            return replace_document_citation(match, citation_to_doc, doc_id_to_info)
                                                        processed_answer = re.sub(r'\[document (\d+)\]', replace_document_citation_local2, processed_answer)
                                                        
                                                        # Remove bottom references section (since we display complete reference list below)
                                                        processed_answer = re.sub(r'\n\nReferences:.*$', '', processed_answer, flags=re.DOTALL)
                                                        
                                                        # Then process consecutive citations, add separators
                                                        processed_answer = re.sub(r'\](\[)', r'], \1', processed_answer)
                                                    
                                                    st.markdown(processed_answer)
                                                    
                                                    # Display citation information (moved below final answer)
                                                    if bio_citation_data:
                                                        st.markdown(f"### 📖 References ({len(bio_citation_data)} citations)")
                                                        
                                                        # Create docId to literature info mapping
                                                        doc_id_to_info = {}
                                                        # Add PubMed data
                                                        for search_data in bio_search_data:
                                                            bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                            for doc in bio_docs:
                                                                doc_id_to_info[doc.get('docId')] = doc
                                                        # Add web search data
                                                        for search_data in web_search_data:
                                                            web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                            for doc in web_docs:
                                                                doc_id_to_info[doc.get('docId')] = doc
                                                        
                                                        # Display citation list, associate with literature info (standard reference format)
                                                        for citation in bio_citation_data:
                                                            doc_id = citation.get('docId')
                                                            citation_num = citation.get('citation')
                                                            source = citation.get('source', '')
                                                            
                                                            if doc_id in doc_id_to_info:
                                                                doc_info = doc_id_to_info[doc_id]
                                                                title = doc_info.get('title', 'N/A')
                                                                url = doc_info.get('url', '#')
                                                                
                                                                if source == 'webSearch':
                                                                    # Web citation format: [number] title. [link](URL)
                                                                    st.markdown(f"[{citation_num}] {title}. [Link]({url})")
                                                                else:
                                                                    # PubMed literature citation format: [number] author. title. journal info. [link](URL)
                                                                    author = doc_info.get('author', 'N/A')
                                                                    journal = doc_info.get('JournalInfo', 'N/A')
                                                                    
                                                                    # Process author info, only show first 3
                                                                    authors = author.split(', ')
                                                                    if len(authors) > 3:
                                                                        display_author = ', '.join(authors[:3]) + ' et al.'
                                                                    else:
                                                                        display_author = author
                                                                    
                                                                    st.markdown(f"[{citation_num}] {display_author}. {title}. {journal}. [Link]({url})")
                                                            else:
                                                                st.markdown(f"[{citation_num}] Document ID: {doc_id}")
                                                    
                                                # Build complete formatted content for saving
                                                complete_content = ""
                                                
                                                # Add analysis information
                                                if bio_search_data or web_search_data:
                                                    total_bio_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in bio_search_data)
                                                    total_web_docs = sum(len(data.get('handlerParam', {}).get('bioDocs', [])) for data in web_search_data)
                                                    if total_bio_docs > 0 and total_web_docs > 0:
                                                        complete_content += f"### 📚 Analysis based on {total_bio_docs} scientific papers and {total_web_docs} web pages\n\n"
                                                    elif total_bio_docs > 0:
                                                        complete_content += f"### 📚 Analysis based on {total_bio_docs} scientific papers\n\n"
                                                    else:
                                                        complete_content += f"### 🌐 Analysis based on {total_web_docs} web pages\n\n"
                                                
                                                # Add final answer
                                                complete_content += "### 🎯 Final Answer\n\n"
                                                complete_content += processed_answer + "\n\n"
                                                
                                                # Add references
                                                if bio_citation_data:
                                                    complete_content += f"### 📖 References ({len(bio_citation_data)} citations)\n\n"
                                                    
                                                    # Create docId to literature info mapping
                                                    doc_id_to_info = {}
                                                    # Add PubMed data
                                                    for search_data in bio_search_data:
                                                        bio_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                        for doc in bio_docs:
                                                            doc_id_to_info[doc.get('docId')] = doc
                                                    # Add web search data
                                                    for search_data in web_search_data:
                                                        web_docs = search_data.get('handlerParam', {}).get('bioDocs', [])
                                                        for doc in web_docs:
                                                            doc_id_to_info[doc.get('docId')] = doc
                                                    
                                                    # Add citation list to complete content
                                                    for citation in bio_citation_data:
                                                        doc_id = citation.get('docId')
                                                        citation_num = citation.get('citation')
                                                        source = citation.get('source', '')
                                                        
                                                        if doc_id in doc_id_to_info:
                                                            doc_info = doc_id_to_info[doc_id]
                                                            title = doc_info.get('title', 'N/A')
                                                            url = doc_info.get('url', '#')
                                                            
                                                            if source == 'webSearch':
                                                                complete_content += f"[{citation_num}] {title}. [Link]({url})\n\n"
                                                            else:
                                                                author = doc_info.get('author', 'N/A')
                                                                journal = doc_info.get('JournalInfo', 'N/A')
                                                                
                                                                authors = author.split(', ')
                                                                if len(authors) > 3:
                                                                    display_author = ', '.join(authors[:3]) + ' et al.'
                                                                else:
                                                                    display_author = author
                                                                
                                                                complete_content += f"[{citation_num}] {display_author}. {title}. {journal}. [Link]({url})\n\n"
                                                        else:
                                                            complete_content += f"[{citation_num}] Document ID: {doc_id}\n\n"
                                                
                                                # Override output and bio_final_answer_content for session recording
                                                output = complete_content
                                                bio_final_answer_content = complete_content
                                                # Set flag to skip LLM processing
                                                has_bio_final_answer = True

                                                # Add download buttons for Bio QA final answer (with complete content)
                                                st.markdown("---")
                                                st.markdown("### 📥 Download Options")
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    create_download_button(complete_content, "bio_qa_report", "md", "bio_qa_stream_chat")
                                                with col2:
                                                    create_download_button(complete_content, "bio_qa_report", "pdf", "bio_qa_stream_chat")

                                                # Save ToolMessage first, then complete formatted content
                                                _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                                                _append_message_to_session({'role': 'assistant', 'content': complete_content})
                                                
                                                # Force immediate rerender so Download Options appear right away
                                                st.rerun()

                                                # Debug: log ToolMessage save
                                                logger.log_system_status(f"Saved ToolMessage for bio_qa_stream_chat: {len(msg.content)} characters")
                                                logger.log_system_status(f"Current chat has {len(st.session_state.get('messages', []))} messages")
                                            else:
                                                # Fallback: if final answer not parsed, display tool message in original way
                                                with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                    st.code(msg.content, language='yaml')
                                                _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                                        elif msg.name == "review_generate":
                                            # Try to extract final report
                                            extracted_report = extract_review_final_report(msg.content)
                                            if extracted_report:
                                                # Always display ToolMessage (collapsible)
                                                with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                    st.code(msg.content, language='yaml')
                                                
                                                # Display final report in main conversation area
                                                with messages_container.chat_message("assistant"):
                                                    st.markdown("---")
                                                    st.markdown("### 📚 Literature Review Report")
                                                    st.markdown(extracted_report)
                                                    
                                                    # Add download buttons to main conversation area (persistent)
                                                    st.markdown("---")
                                                    st.markdown("### 📥 Download Options")
                                                    col1, col2 = st.columns(2)
                                                    with col1:
                                                        create_download_button(extracted_report, "literature_review", "md", "review_generate")
                                                    with col2:
                                                        create_download_button(extracted_report, "literature_review", "pdf", "review_generate")
                                                
                                                # Override output and review_final_report_content for session recording
                                                output = extracted_report
                                                review_final_report_content = extracted_report
                                                # Set flag to skip LLM processing
                                                has_review_final_report = True

                                                # Save "assistant final report" to session history (instead of writing tool original text to tool field)
                                                _append_message_to_session({'role': 'assistant', 'content': extracted_report})
                                                # Also save the original ToolMessage for reference
                                                _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                                                
                                                # Force immediate rerender so Download Options appear right away
                                                st.rerun()
                                            else:
                                                # Fallback: if final report not parsed, display tool message in original way
                                                with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                    st.code(msg.content, language='yaml')
                                                _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                                        else:
                                            # Other tools remain the same, but use collapsible display
                                            with st.expander(f"🔧 ToolMessage - {tool_count} ({msg.name})", expanded=False):
                                                st.code(msg.content, language='yaml')
                                            _append_message_to_session({'role': 'assistant', 'content': '', 'tool': msg.content})
                            else:  # AIMessage
                                # If there's a final answer or final report, skip LLM response
                                if not has_bio_final_answer and not has_review_final_report and hasattr(msg, "content") and msg.content:
                                    with messages_container.chat_message("assistant"):
                                        output = str(msg.content)
                                        st.markdown(output)
                    
                    # Ensure final answer or final report is correctly saved
                    if not output and bio_final_answer_content:
                        output = bio_final_answer_content
                    if not output and review_final_report_content:
                        output = review_final_report_content
                    
                    # Initialize response_dct
                    response_dct = None
                    
                    # If there's a final answer or final report, use it directly as response, no need to save additional assistant message
                    if has_bio_final_answer or has_review_final_report:
                        # Final answer or final report has already been saved to session history during processing
                        # But we need to trigger UI re-render to show the saved content
                        if has_bio_final_answer:
                            response_dct = {"role": "assistant", "content": bio_final_answer_content}
                            logger.log_chat_message("assistant", bio_final_answer_content, st.session_state.get('current_chat_id'), has_tool=True)
                        elif has_review_final_report:
                            response_dct = {"role": "assistant", "content": review_final_report_content}
                            logger.log_chat_message("assistant", review_final_report_content, st.session_state.get('current_chat_id'), has_tool=True)
                    else:
                        response_dct = {"role": "assistant", "content": output}
                        # Log assistant message
                        logger.log_chat_message("assistant", output, st.session_state.get('current_chat_id'))
                # Fall back to regular stream response if agent not available
                else:
                    st.warning("You are not connect to MCP servers!")
                    response_stream = get_response_stream(
                        main_prompt,
                        llm_provider=st.session_state['params']['model_id'],
                        system=system_prompt,
                        temperature=st.session_state['params'].get('temperature', DEFAULT_TEMPERATURE),
                        max_tokens=st.session_state['params'].get('max_tokens', DEFAULT_MAX_TOKENS), 
                    )         
                    with messages_container.chat_message("assistant"):
                        response = st.write_stream(response_stream)
                        response_dct = {"role": "assistant", "content": response}
            except Exception as e:
                # Stop monitoring and log error
                task_monitor.stop_monitoring(task_id)
                duration = time.time() - start_time
                
                response = f"⚠️ Something went wrong: {str(e)}"
                logger.log_error(
                    "MCP_Agent_Error",
                    str(e),
                    {
                        'chat_id': st.session_state.get('current_chat_id'),
                        'duration_seconds': duration,
                        'user_text': user_text
                    }
                )
                
                st.error(response)
                st.code(traceback.format_exc(), language="python")
                st.stop()
            finally:
                # Stop monitoring
                task_monitor.stop_monitoring(task_id)
        # Add assistant message to chat history (only if not already saved)
        if response_dct is not None:
            # Check if this is a final answer/report that was already saved during processing
            if (has_bio_final_answer or has_review_final_report) and response_dct.get('content'):
                # Don't save again, just trigger UI re-render
                pass
            else:
                _append_message_to_session(response_dct)
            
    display_tool_executions()