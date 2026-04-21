"""
Task management routes: list, get, delete tasks.
"""
from fastapi import APIRouter, HTTPException, Depends

from app.services.task_service import task_manager
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(user_id: str = Depends(get_current_user)):
    return task_manager.get_all_tasks(user_id)


@router.get("/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    deleted = task_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "任务已删除", "taskId": task_id}
