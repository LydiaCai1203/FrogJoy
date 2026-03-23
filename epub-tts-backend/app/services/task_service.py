"""
后台任务服务 - 管理异步任务
"""
import asyncio
import uuid
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

TASKS_FILE = "data/tasks.json"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskManager:
    """任务管理器 - 单例模式"""
    _instance = None
    _tasks: Dict[str, Dict] = {}
    _running_tasks: Dict[str, asyncio.Task] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_tasks()
        return cls._instance
    
    def _load_tasks(self):
        """从文件加载任务状态"""
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._tasks = data.get("tasks", {})
                    # 将运行中的任务标记为失败（服务重启后）
                    for task_id, task in self._tasks.items():
                        if task["status"] == TaskStatus.RUNNING:
                            task["status"] = TaskStatus.FAILED
                            task["error"] = "服务重启，任务中断"
            except (json.JSONDecodeError, IOError):
                self._tasks = {}
        else:
            self._tasks = {}
    
    def _save_tasks(self):
        """保存任务状态到文件"""
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"tasks": self._tasks}, f, ensure_ascii=False, indent=2)
    
    def create_task(self, task_type: str, params: Dict[str, Any], title: str = "") -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "title": title,
            "params": params,
            "status": TaskStatus.PENDING,
            "progress": 0,
            "progressText": "等待开始...",
            "result": None,
            "error": None,
            "createdAt": datetime.now().isoformat(),
            "startedAt": None,
            "completedAt": None
        }
        self._save_tasks()
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务（按创建时间倒序）"""
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return tasks
    
    def update_task(self, task_id: str, **kwargs):
        """更新任务状态"""
        if task_id in self._tasks:
            self._tasks[task_id].update(kwargs)
            self._save_tasks()
    
    def start_task(self, task_id: str):
        """标记任务开始"""
        self.update_task(
            task_id,
            status=TaskStatus.RUNNING,
            startedAt=datetime.now().isoformat()
        )
    
    def complete_task(self, task_id: str, result: Any):
        """标记任务完成"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            progressText="完成",
            result=result,
            completedAt=datetime.now().isoformat()
        )
    
    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=error,
            completedAt=datetime.now().isoformat()
        )
    
    def update_progress(self, task_id: str, progress: int, text: str = ""):
        """更新任务进度"""
        self.update_task(task_id, progress=progress, progressText=text)
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            # 如果任务正在运行，取消它
            if task_id in self._running_tasks:
                self._running_tasks[task_id].cancel()
                del self._running_tasks[task_id]
            del self._tasks[task_id]
            self._save_tasks()
            return True
        return False
    
    def register_running_task(self, task_id: str, task: asyncio.Task):
        """注册正在运行的异步任务"""
        self._running_tasks[task_id] = task
    
    def unregister_running_task(self, task_id: str):
        """取消注册运行中的任务"""
        if task_id in self._running_tasks:
            del self._running_tasks[task_id]


# 全局任务管理器实例
task_manager = TaskManager()

