import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import json


class ChatLogger:
    """
    聊天应用的关键日志记录器
    """
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self._ensure_log_dir()
        self._setup_loggers()
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def _setup_loggers(self):
        """设置不同类型的日志记录器"""
        # 用户行为日志
        self.user_logger = logging.getLogger('user_actions')
        self.user_logger.setLevel(logging.INFO)
        # 防止重复日志
        self.user_logger.handlers.clear()
        
        user_handler = logging.FileHandler(
            os.path.join(self.log_dir, 'user_actions.log'),
            encoding='utf-8'
        )
        user_formatter = logging.Formatter(
            '📝 %(asctime)s - %(levelname)s - %(message)s'
        )
        user_handler.setFormatter(user_formatter)
        self.user_logger.addHandler(user_handler)
        
        # 添加控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(user_formatter)
        self.user_logger.addHandler(console_handler)
        
        # MCP服务日志
        self.mcp_logger = logging.getLogger('mcp_services')
        self.mcp_logger.setLevel(logging.INFO)
        # 防止重复日志
        self.mcp_logger.handlers.clear()
        
        mcp_handler = logging.FileHandler(
            os.path.join(self.log_dir, 'mcp_services.log'),
            encoding='utf-8'
        )
        mcp_formatter = logging.Formatter(
            '🔧 %(asctime)s - %(levelname)s - %(message)s'
        )
        mcp_handler.setFormatter(mcp_formatter)
        self.mcp_logger.addHandler(mcp_handler)
        
        # 添加控制台输出
        mcp_console_handler = logging.StreamHandler()
        mcp_console_handler.setFormatter(mcp_formatter)
        self.mcp_logger.addHandler(mcp_console_handler)
        
        # 系统状态日志
        self.system_logger = logging.getLogger('system_status')
        self.system_logger.setLevel(logging.INFO)
        # 防止重复日志
        self.system_logger.handlers.clear()
        
        system_handler = logging.FileHandler(
            os.path.join(self.log_dir, 'system_status.log'),
            encoding='utf-8'
        )
        system_formatter = logging.Formatter(
            '🏥 %(asctime)s - %(levelname)s - %(message)s'
        )
        system_handler.setFormatter(system_formatter)
        self.system_logger.addHandler(system_handler)
        
        # 添加控制台输出
        system_console_handler = logging.StreamHandler()
        system_console_handler.setFormatter(system_formatter)
        self.system_logger.addHandler(system_console_handler)
        
        # 错误日志
        self.error_logger = logging.getLogger('errors')
        self.error_logger.setLevel(logging.ERROR)
        # 防止重复日志
        self.error_logger.handlers.clear()
        
        error_handler = logging.FileHandler(
            os.path.join(self.log_dir, 'errors.log'),
            encoding='utf-8'
        )
        error_formatter = logging.Formatter(
            '❌ %(asctime)s - %(levelname)s - %(message)s'
        )
        error_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_handler)
        
        # 添加控制台输出
        error_console_handler = logging.StreamHandler()
        error_console_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_console_handler)
    
    def log_user_action(self, action: str, details: Optional[Dict[str, Any]] = None):
        """记录用户行为"""
        message = f"USER_ACTION: {action}"
        if details:
            message += f" - Details: {json.dumps(details, ensure_ascii=False)}"
        self.user_logger.info(message)
    
    def log_mcp_connection(self, server_name: str, server_url: str, success: bool, error: Optional[str] = None):
        """记录MCP服务器连接"""
        status = "SUCCESS" if success else "FAILED"
        message = f"MCP_CONNECTION: {server_name} ({server_url}) - {status}"
        if error:
            message += f" - Error: {error}"
        self.mcp_logger.info(message)
    
    def log_mcp_tool_call(self, tool_name: str, input_data: Dict[str, Any], chat_id: Optional[str] = None):
        """记录MCP工具调用"""
        message = f"MCP_TOOL_CALL: {tool_name}"
        if chat_id:
            message += f" - ChatID: {chat_id}"
        message += f" - Input: {json.dumps(input_data, ensure_ascii=False)}"
        self.mcp_logger.info(message)
    
    def log_mcp_tool_response(self, tool_name: str, response_data: Any, chat_id: Optional[str] = None):
        """记录MCP工具响应"""
        message = f"MCP_TOOL_RESPONSE: {tool_name}"
        if chat_id:
            message += f" - ChatID: {chat_id}"
        
        # 对于大型响应，只记录摘要
        if isinstance(response_data, str) and len(response_data) > 1000:
            message += f" - Response: {response_data[:500]}... (truncated, total length: {len(response_data)})"
        else:
            message += f" - Response: {json.dumps(response_data, ensure_ascii=False)}"
        
        self.mcp_logger.info(message)
    
    def log_mcp_agent_usage(self, agent_type: str, tools_used: List[str], chat_id: Optional[str] = None):
        """记录MCP代理使用情况"""
        if agent_type == "ReactAgent":
            message = f"MCP_AGENT_AVAILABLE: {agent_type}"
            if chat_id:
                message += f" - ChatID: {chat_id}"
            message += f" - Available Tools: {', '.join(tools_used)}"
        else:
            message = f"MCP_AGENT_USAGE: {agent_type}"
            if chat_id:
                message += f" - ChatID: {chat_id}"
            message += f" - Tools Used: {', '.join(tools_used)}"
        self.mcp_logger.info(message)
    
    def log_chat_message(self, role: str, content: str, chat_id: Optional[str] = None, has_tool: bool = False):
        """记录聊天消息"""
        message = f"CHAT_MESSAGE: {role.upper()}"
        if chat_id:
            message += f" - ChatID: {chat_id}"
        if has_tool:
            message += " - HasTool: True"
        
        # 对于长消息，只记录摘要
        if len(content) > 500:
            message += f" - Content: {content[:200]}... (truncated, total length: {len(content)})"
        else:
            message += f" - Content: {content}"
        
        self.user_logger.info(message)
    
    def log_llm_test(self, provider: str, success: bool, error: Optional[str] = None):
        """记录LLM连接测试"""
        status = "SUCCESS" if success else "FAILED"
        message = f"LLM_TEST: {provider} - {status}"
        if error:
            message += f" - Error: {error}"
        self.system_logger.info(message)
    
    def log_system_status(self, status: str, details: Optional[Dict[str, Any]] = None):
        """记录系统状态"""
        message = f"SYSTEM_STATUS: {status}"
        if details:
            message += f" - Details: {json.dumps(details, ensure_ascii=False)}"
        self.system_logger.info(message)
    
    def log_error(self, error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None):
        """记录错误"""
        message = f"ERROR: {error_type} - {error_message}"
        if context:
            message += f" - Context: {json.dumps(context, ensure_ascii=False)}"
        self.error_logger.error(message)
    
    def log_long_running_task(self, task_name: str, duration_seconds: float, chat_id: Optional[str] = None):
        """记录长时间运行的任务"""
        message = f"LONG_RUNNING_TASK: {task_name} - Duration: {duration_seconds:.2f}s"
        if chat_id:
            message += f" - ChatID: {chat_id}"
        self.system_logger.info(message)


# 全局日志记录器实例
chat_logger = ChatLogger()


def get_logger():
    """获取全局日志记录器"""
    return chat_logger 