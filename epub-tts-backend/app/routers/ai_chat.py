"""
AI chat route: multi-round chat with SSE streaming.
"""
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from shared.schemas.ai import ChatRequest
from app.services.ai.provider import AIService, ChatMessage
from app.routers.ai_config import _build_ai_config
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import check_guest_rate_limit

router = APIRouter(prefix="/ai", tags=["ai-chat"])


@router.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """
    Multi-round chat endpoint using SSE (Server-Sent Events) for streaming.
    """
    check_guest_rate_limit(user_id, "chat")
    ai_config = _build_ai_config(user_id)
    messages = [ChatMessage(role=m.role, content=m.content) for m in request.messages]

    async def stream():
        service = AIService(ai_config)
        try:
            async for chunk in service.chat_stream(messages):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
