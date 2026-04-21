"""
概念提取 API —— 管理书籍的概念索引和角标数据

端点:
  POST   /api/books/{book_id}/concepts/build          触发概念提取 (异步后台)
  GET    /api/books/{book_id}/concepts/status          概念提取状态
  GET    /api/books/{book_id}/concepts                 获取概念列表
  GET    /api/books/{book_id}/concepts/by-chapter/{chapter_idx}
                                                       某章的概念角标数据
  GET    /api/books/{book_id}/concepts/{concept_id}    单个概念详情
  DELETE /api/books/{book_id}/concepts                 删除概念数据
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger

from app.middleware.auth import get_current_user
from app.services.concept_service import ConceptService

router = APIRouter(prefix="/books", tags=["concepts"])


# ---------- Build ----------

@router.post("/{book_id}/concepts/build")
async def build_concepts(
    book_id: str,
    background: BackgroundTasks,
    rebuild: bool = Query(False, description="True 时强制重建"),
    user_id: str = Depends(get_current_user),
):
    """
    触发概念提取。后台运行三阶段流水线, 本端点立即返回。

    前端轮询 GET /concepts/status, concept_status 变为 'enriched' 后可查概念。
    """
    status = ConceptService.get_status(book_id, user_id)

    if status and status["concept_status"] == "enriched" and not rebuild:
        return {"message": "already enriched", **status}

    if status and status["concept_status"] == "extracting":
        return {"message": "already extracting", **status}

    background.add_task(
        _build_concepts_bg, book_id=book_id, user_id=user_id, rebuild=rebuild
    )
    return {
        "message": "concept extraction started",
        "concept_status": "extracting",
    }


def _build_concepts_bg(book_id: str, user_id: str, rebuild: bool):
    try:
        ConceptService.build_concepts(book_id, user_id, rebuild)
    except Exception:
        logger.exception("Concept extraction crashed")


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
    """
    返回某章的概念角标数据, 前端用于渲染 ① ② ③ 角标和悬浮弹窗。

    只返回在当前章及之前有 definition/refinement 的概念 (防剧透)。
    """
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
