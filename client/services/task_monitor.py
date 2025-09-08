import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from services.logging_service import get_logger


class LongRunningTaskMonitor:
    """
    长时间运行任务监控器，用于在MCP工具执行期间定期发送心跳
    """
    
    def __init__(self, heartbeat_interval: int = 300):  # 5分钟 = 300秒
        self.heartbeat_interval = heartbeat_interval
        self.logger = get_logger()
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
    
    def start_monitoring(self, task_id: str, task_name: str, chat_id: Optional[str] = None, 
                        heartbeat_callback: Optional[Callable] = None):
        """
        开始监控一个长时间运行的任务
        
        Args:
            task_id: 任务唯一标识
            task_name: 任务名称
            chat_id: 聊天ID
            heartbeat_callback: 心跳回调函数
        """
        self.active_tasks[task_id] = {
            'task_name': task_name,
            'chat_id': chat_id,
            'start_time': time.time(),
            'heartbeat_callback': heartbeat_callback,
            'last_heartbeat': time.time(),
            'heartbeat_count': 0
        }
        
        self.logger.log_system_status(
            f"Started monitoring long-running task: {task_name}",
            {'task_id': task_id, 'chat_id': chat_id}
        )
    
    def stop_monitoring(self, task_id: str):
        """
        停止监控一个任务
        
        Args:
            task_id: 任务唯一标识
        """
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            duration = time.time() - task_info['start_time']
            
            self.logger.log_long_running_task(
                task_info['task_name'],
                duration,
                task_info['chat_id']
            )
            
            del self.active_tasks[task_id]
    
    async def send_heartbeat(self, task_id: str):
        """
        发送心跳信号
        
        Args:
            task_id: 任务唯一标识
        """
        if task_id not in self.active_tasks:
            return
        
        task_info = self.active_tasks[task_id]
        current_time = time.time()
        
        # 检查是否需要发送心跳
        if current_time - task_info['last_heartbeat'] >= self.heartbeat_interval:
            task_info['last_heartbeat'] = current_time
            task_info['heartbeat_count'] += 1
            
            duration = current_time - task_info['start_time']
            
            # 记录心跳日志
            self.logger.log_system_status(
                f"Heartbeat for long-running task: {task_info['task_name']}",
                {
                    'task_id': task_id,
                    'chat_id': task_info['chat_id'],
                    'duration_seconds': duration,
                    'heartbeat_count': task_info['heartbeat_count']
                }
            )
            
            # 执行心跳回调
            if task_info['heartbeat_callback']:
                try:
                    await task_info['heartbeat_callback'](task_id, task_info)
                except Exception as e:
                    self.logger.log_error(
                        "HeartbeatCallbackError",
                        str(e),
                        {'task_id': task_id, 'task_name': task_info['task_name']}
                    )
    
    async def monitor_all_tasks(self):
        """
        监控所有活跃任务并发送心跳
        """
        while True:
            try:
                # 为每个活跃任务发送心跳
                for task_id in list(self.active_tasks.keys()):
                    await self.send_heartbeat(task_id)
                
                # 等待下一次检查
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                self.logger.log_error(
                    "TaskMonitorError",
                    str(e),
                    {'active_tasks_count': len(self.active_tasks)}
                )
                await asyncio.sleep(60)  # 出错后等待1分钟再继续
    
    def get_active_tasks_info(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有活跃任务的信息
        
        Returns:
            活跃任务信息字典
        """
        result = {}
        current_time = time.time()
        
        for task_id, task_info in self.active_tasks.items():
            duration = current_time - task_info['start_time']
            result[task_id] = {
                'task_name': task_info['task_name'],
                'chat_id': task_info['chat_id'],
                'duration_seconds': duration,
                'heartbeat_count': task_info['heartbeat_count'],
                'last_heartbeat_seconds_ago': current_time - task_info['last_heartbeat']
            }
        
        return result


# 全局任务监控器实例
task_monitor = LongRunningTaskMonitor()


def get_task_monitor():
    """获取全局任务监控器"""
    return task_monitor


async def start_task_monitoring():
    """启动任务监控"""
    monitor = get_task_monitor()
    await monitor.monitor_all_tasks() 