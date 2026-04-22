"""
概念提取 API — 管理书籍的概念索引和角标数据

提取任务通过 A2A 协议委托给 agent-server。
查询接口在 backend 本地执行。

端点:
  POST   /api/books/{book_id}/concepts/build          触发概念提取 (A2A)
  GET    /api/books/{book_id}/concepts/status          概念提取状态
  POST   /api/books/{book_id}/concepts/cancel          取消概念提取
  GET    /api/books/{book_id}/concepts                 获取概念列表
  GET    /api/books/{book_id}/concepts/by-chapter/{chapter_idx}
                                                       某章的概念角标数据
  GET    /api/books/{book_id}/concepts/{concept_id}    单个概念详情
  DELETE /api/books/{book_id}/concepts                 删除概念数据
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.middleware.auth import get_current_user
from app.services.concept_service import ConceptService

router = APIRouter(prefix="/books", tags=["concepts"])


# ---------- Build ----------

@router.post("/{book_id}/concepts/build")
async def build_concepts(
    book_id: str,
    rebuild: bool = Query(False, description="True 时强制重建"),
    user_id: str = Depends(get_current_user),
):
    """
    触发概念提取。通过 A2A 协议委托给 agent-server, 本端点立即返回。

    前端轮询 GET /concepts/status, concept_status 变为 'enriched' 后可查概念。
    """
    status = ConceptService.get_status(book_id, user_id)

    if status and status["concept_status"] == "enriched" and not rebuild:
        return {"message": "already enriched", **status}

    if status and status["concept_status"] == "extracting":
        return {"message": "already extracting", **status}

    try:
        task_id = ConceptService.build_concepts(book_id, user_id, rebuild)
        if task_id is None:
            return {"message": "already enriched", "concept_status": "enriched"}
        return {
            "message": "concept extraction started",
            "concept_status": "extracting",
            "task_id": task_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start concept extraction")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Cancel ----------

@router.post("/{book_id}/concepts/cancel")
async def cancel_extraction(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    """取消正在进行的概念提取。"""
    cancelled = ConceptService.cancel_extraction(book_id, user_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="No running extraction found")
    return {"message": "cancel requested"}


# ---------- Query ----------

@router.get("/{book_id}/concepts/status")
async def get_concept_status(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    status = ConceptService.get_status(book_id, user_id)
    if not status:
        return {"concept_status": None}
    return status


@router.get("/{book_id}/concepts")
async def list_concepts(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    return {
        "book_id": book_id,
        "concepts": ConceptService.get_concepts(book_id, user_id),
    }


@router.get("/{book_id}/concepts/by-chapter/{chapter_idx}")
async def get_chapter_annotations(
    book_id: str,
    chapter_idx: int,
    user_id: str = Depends(get_current_user),
):
    """返回某章的概念角标数据, 前端用于渲染角标和悬浮弹窗。"""
    annotations = ConceptService.get_chapter_annotations(
        book_id, user_id, chapter_idx
    )
    return {
        "book_id": book_id,
        "chapter_idx": chapter_idx,
        "annotations": annotations,
    }


@router.get("/{book_id}/concepts/{concept_id}")
async def get_concept_detail(
    book_id: str,
    concept_id: str,
    user_id: str = Depends(get_current_user),
):
    detail = ConceptService.get_concept_detail(concept_id, user_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Concept not found")
    return detail


# ---------- Delete ----------

@router.delete("/{book_id}/concepts")
async def delete_concepts(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    deleted = ConceptService.delete_concepts(book_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No concepts found")
    return {"message": "concepts deleted", "book_id": book_id}
