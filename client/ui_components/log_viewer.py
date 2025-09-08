import streamlit as st
import os
from datetime import datetime, timedelta
from services.logging_service import get_logger
from services.task_monitor import get_task_monitor


def create_log_viewer():
    """
    创建日志查看器组件
    """
    st.markdown("## 📊 System Logs")
    
    # 日志类型选择
    log_types = {
        "User Actions": "user_actions.log",
        "MCP Services": "mcp_services.log", 
        "System Status": "system_status.log",
        "Errors": "errors.log"
    }
    
    selected_log = st.selectbox(
        "Select Log Type",
        options=list(log_types.keys()),
        index=1  # 默认选择MCP Services
    )
    
    # 时间范围选择
    time_ranges = {
        "Last Hour": 1,
        "Last 6 Hours": 6,
        "Last 24 Hours": 24,
        "Last 7 Days": 168,
        "All": 0
    }
    
    selected_range = st.selectbox(
        "Time Range",
        options=list(time_ranges.keys()),
        index=2
    )
    
    # 显示日志内容
    log_file = log_types[selected_log]
    log_path = os.path.join("logs", log_file)
    
    if os.path.exists(log_path):
        # 读取日志文件
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 过滤时间范围
        if time_ranges[selected_range] > 0:
            cutoff_time = datetime.now() - timedelta(hours=time_ranges[selected_range])
            filtered_lines = []
            
            for line in lines:
                try:
                    # 解析时间戳
                    timestamp_str = line.split(' - ')[0]
                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    if log_time >= cutoff_time:
                        filtered_lines.append(line)
                except:
                    # 如果无法解析时间戳，保留该行
                    filtered_lines.append(line)
            
            lines = filtered_lines
        
        # 显示日志
        if lines:
            st.markdown(f"**Showing {len(lines)} log entries**")
            
            # 搜索功能
            search_term = st.text_input("Search in logs (e.g., 'bio_qa_stream_chat', 'review_generate')", "")
            if search_term:
                lines = [line for line in lines if search_term.lower() in line.lower()]
                st.markdown(f"**Found {len(lines)} matching entries**")
            
            # 显示日志内容
            if lines:
                # 只显示最后1000行以避免性能问题
                display_lines = lines[-1000:] if len(lines) > 1000 else lines
                
                st.text_area(
                    "Log Content",
                    value=''.join(display_lines),
                    height=400,
                    disabled=True
                )
                
                if len(lines) > 1000:
                    st.info(f"Showing last 1000 lines of {len(lines)} total entries")
            else:
                st.info("No log entries found matching the criteria")
        else:
            st.info("No log entries found in the selected time range")
    else:
        st.warning(f"Log file {log_file} not found")


def create_system_status_dashboard():
    """
    创建系统状态仪表板
    """
    st.markdown("## 🏥 System Status Dashboard")
    
    logger = get_logger()
    task_monitor = get_task_monitor()
    
    # 获取活跃任务信息
    active_tasks = task_monitor.get_active_tasks_info()
    
    # 显示活跃任务
    if active_tasks:
        st.markdown("### 🔄 Active Long-Running Tasks")
        for task_id, task_info in active_tasks.items():
            with st.expander(f"Task: {task_info['task_name']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Duration", f"{task_info['duration_seconds']:.1f}s")
                with col2:
                    st.metric("Heartbeats", task_info['heartbeat_count'])
                with col3:
                    st.metric("Last Heartbeat", f"{task_info['last_heartbeat_seconds_ago']:.1f}s ago")
                
                if task_info['chat_id']:
                    st.info(f"Chat ID: {task_info['chat_id']}")
    else:
        st.info("No active long-running tasks")
    
    # 显示系统统计信息
    st.markdown("### 📈 System Statistics")
    
    # 这里可以添加更多系统统计信息
    # 比如：总对话数、总消息数、MCP工具调用次数等
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Chats", len(st.session_state.get("history_chats", [])))
    with col2:
        total_messages = sum(len(chat.get('messages', [])) for chat in st.session_state.get("history_chats", []))
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("MCP Tools", len(st.session_state.get("tools", [])))


def create_log_management():
    """
    创建日志管理功能
    """
    st.markdown("## 🔧 Log Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Download All Logs"):
            # 这里可以实现下载所有日志文件的功能
            st.info("Log download feature coming soon...")
    
    with col2:
        if st.button("🗑️ Clear Old Logs"):
            # 这里可以实现清理旧日志的功能
            st.info("Log cleanup feature coming soon...")


def main():
    """
    主日志管理界面
    """
    st.title("📊 System Monitoring & Logs")
    
    # 创建选项卡
    tab1, tab2, tab3 = st.tabs(["📋 Logs", "🏥 Status", "🔧 Management"])
    
    with tab1:
        create_log_viewer()
    
    with tab2:
        create_system_status_dashboard()
    
    with tab3:
        create_log_management() 