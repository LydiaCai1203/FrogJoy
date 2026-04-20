"""
Book Index API —— 管理书籍的段落级索引

端点:
  POST   /api/books/{book_id}/index          触发构建索引 (异步)
  GET    /api/books/{book_id}/index/status   查询索引状态
  GET    /api/books/{book_id}/index/chapters 章节目录 (带段落计数)
  GET    /api/books/{book_id}/index/paragraphs[?chapter_idx=N]
                                             拉段落 (可按章过滤)
  DELETE /api/books/{book_id}/index          删除索引

所有端点都是 per-user 的 (user_id 从 token 取), 不会跨用户看到他人数据。

注: 当前 v0 索引只包含 paragraphs + paragraph_id. Extractor (LLM 术语抽取)
等 API key 配置到位后独立接入, 走同一个 build_index 流程但多一个 phase.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger

from app.middleware.auth import get_current_user
from app.services.index_service import IndexService

router = APIRouter(prefix="/books", tags=["index"])


# ---------- Build ----------

@router.post("/{book_id}/index")
async def build_index(
    book_id: str,
    background: BackgroundTasks,
    rebuild: bool = Query(False, description="True 时强制重建"),
    user_id: str = Depends(get_current_user),
):
    """
    触发索引构建。实际解析在后台运行, 本端点立即返回当前状态。

    典型流程:
      1. 前端调 POST /api/books/{id}/index
      2. 返回 {status: 'parsing', ...}
      3. 前端轮询 GET /api/books/{id}/index/status
      4. status 变为 'parsed' 后可查 paragraphs
    """
    # 先同步启动 (确保 pending 记录存在), 真正的解析异步
    current = IndexService.get_status(book_id, user_id)

    if current and current["status"] == "parsed" and not rebuild:
        return {
            "message": "already parsed",
            **current,
        }

    if current and current["status"] == "parsing":
        return {
            "message": "already parsing",
            **current,
        }

    # 后台跑
    background.add_task(
        _build_index_bg, book_id=book_id, user_id=user_id, rebuild=rebuild
    )
    return {
        "message": "indexing started",
        "book_id": book_id,
        "status": "parsing",
    }


def _build_index_bg(book_id: str, user_id: str, rebuild: bool):
    """后台任务: 错误只记日志, 状态写进 IndexedBook.error_message"""
    try:
        IndexService.build_index(
            book_id=book_id, user_id=user_id, rebuild=rebuild
        )
    except HTTPException as e:
        logger.error(f"Index build HTTPException: {e.detail}")
    except Exception:
        logger.exception("Index build crashed")


# ---------- Query ----------

@router.get("/{book_id}/index/status")
async def get_index_status(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    status = IndexService.get_status(book_id, user_id)
    if not status:
        return {
            "book_id": book_id,
            "status": "not_indexed",
        }
    return status


@router.get("/{book_id}/index/chapters")
async def list_chapters(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    status = IndexService.get_status(book_id, user_id)
    if not status or status["status"] != "parsed":
        raise HTTPException(
            status_code=409,
            detail="Index not ready. Call POST /books/{id}/index first.",
        )
    return {
        "book_id": book_id,
        "chapters": IndexService.get_chapters(book_id, user_id),
    }


@router.get("/{book_id}/index/paragraphs")
async def list_paragraphs(
    book_id: str,
    chapter_idx: int | None = Query(None, description="只查某章; 省略拉全书"),
    user_id: str = Depends(get_current_user),
):
    status = IndexService.get_status(book_id, user_id)
    if not status or status["status"] != "parsed":
        raise HTTPException(
            status_code=409,
            detail="Index not ready. Call POST /books/{id}/index first.",
        )
    paragraphs = IndexService.get_paragraphs(
        book_id=book_id, user_id=user_id, chapter_idx=chapter_idx
    )
    return {
        "book_id": book_id,
        "chapter_idx": chapter_idx,
        "count": len(paragraphs),
        "paragraphs": paragraphs,
    }


# ---------- Delete ----------

@router.delete("/{book_id}/index")
async def delete_index(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    deleted = IndexService.delete_index(book_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Index not found")
    return {"message": "index deleted", "book_id": book_id}
