"""
Agent Server — A2A 协议独立服务

概念提取等 agent 通过 A2A 协议对外提供服务。
backend 作为 A2A client 调用。
"""
import os
import sys
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from loguru import logger

# Configure loguru before anything else
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
)

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.routes import (
    create_rest_routes,
    create_agent_card_routes,
)
from a2a.types import AgentCard, AgentSkill

from agents.concept_agent import ConceptAgentExecutor


def create_agent_card() -> AgentCard:
    return AgentCard(
        name="BookReader Agent Server",
        description="BookReader 的 AI Agent 服务, 提供概念提取等能力",
        version="1.0.0",
        skills=[
            AgentSkill(
                id="concept_extraction",
                name="概念提取",
                description="从书籍中提取核心概念、去重合并、关键词匹配",
                tags=["concept", "extraction", "book"],
            ),
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )


def create_app() -> Starlette:
    agent_card = create_agent_card()
    task_store = InMemoryTaskStore()
    agent_executor = ConceptAgentExecutor()

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        agent_card=agent_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_rest_routes(request_handler))

    # Health check
    async def health(request):
        return JSONResponse({"status": "ok"})

    routes.append(Route("/health", health, methods=["GET"]))

    return Starlette(routes=routes)


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("AGENT_SERVER_PORT", "9000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
