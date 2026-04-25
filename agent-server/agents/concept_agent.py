"""
ConceptAgent — A2A AgentExecutor 实现

接收 book_id/user_id, 跑 Phase 0→1→2→3,
通过 event_queue 推送进度。
"""
from __future__ import annotations

import asyncio
import json

from loguru import logger
from google.protobuf import struct_pb2

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    Message,
    Part,
    Role,
)

from services.concept_extraction import ConceptExtractor


class ConceptAgentExecutor(AgentExecutor):
    """A2A AgentExecutor for concept extraction."""

    def __init__(self):
        super().__init__()
        self._cancel_flags: dict[str, bool] = {}

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task_id = context.task_id
        context_id = context.context_id

        # 解析用户消息: 期望 JSON {"book_id": "...", "user_id": "...", "rebuild": false}
        user_input = context.get_user_input()
        try:
            params = json.loads(user_input)
        except (json.JSONDecodeError, TypeError):
            await self._fail(event_queue, task_id, context_id, f"Invalid input: {user_input}")
            return

        book_id = params.get("book_id")
        user_id = params.get("user_id")
        rebuild = params.get("rebuild", False)

        if not book_id or not user_id:
            await self._fail(event_queue, task_id, context_id, "Missing book_id or user_id")
            return

        logger.info(f"ConceptAgent execute: task={task_id} book={book_id} user={user_id}")

        # 先发一个 Task 给框架, 进入异步工作模式
        task = Task(
            id=task_id,
            context_id=context_id,
            status=TaskStatus(
                state=TaskState.TASK_STATE_WORKING,
                message=Message(
                    role=Role.ROLE_AGENT,
                    parts=[Part(text="概念提取已开始")],
                ),
            ),
        )
        await event_queue.enqueue_event(task)

        # 清除之前的取消标志
        self._cancel_flags.pop(task_id, None)

        # progress callback → 发 TaskStatusUpdateEvent
        async def _send_progress(pct: int, text: str):
            # 进度放在 message.metadata 里, text 放在 parts 里
            meta = struct_pb2.Struct()
            meta.update({"progress": pct})
            evt = TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.TASK_STATE_WORKING,
                    message=Message(
                        role=Role.ROLE_AGENT,
                        parts=[Part(text=text)],
                        metadata=meta,
                    ),
                ),
            )
            await event_queue.enqueue_event(evt)

        # 用 asyncio.to_thread 把同步的提取逻辑跑在线程里
        loop = asyncio.get_event_loop()

        # 进度回调需要 bridge sync → async
        def sync_progress(pct: int, text: str):
            asyncio.run_coroutine_threadsafe(_send_progress(pct, text), loop)

        def cancel_check() -> bool:
            return self._cancel_flags.get(task_id, False)

        extractor = ConceptExtractor(
            book_id=book_id,
            user_id=user_id,
            rebuild=rebuild,
            progress_callback=sync_progress,
            cancel_check=cancel_check,
        )

        try:
            result = await asyncio.to_thread(extractor.run)

            # 完成
            result_text = json.dumps(result, ensure_ascii=False)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.TASK_STATE_COMPLETED,
                        message=Message(
                            role=Role.ROLE_AGENT,
                            parts=[Part(text=result_text)],
                        ),
                    ),
                )
            )
            logger.info(f"ConceptAgent done: task={task_id} result={result_text}")

        except InterruptedError:
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.TASK_STATE_CANCELED,
                        message=Message(
                            role=Role.ROLE_AGENT,
                            parts=[Part(text="用户取消了概念提取")],
                        ),
                    ),
                )
            )
            logger.info(f"ConceptAgent cancelled: task={task_id}")

        except Exception as e:
            await self._fail(event_queue, task_id, context_id, str(e), task_already_created=True)
            logger.exception(f"ConceptAgent failed: task={task_id}")

        finally:
            self._cancel_flags.pop(task_id, None)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task_id = context.task_id
        logger.info(f"ConceptAgent cancel requested: task={task_id}")
        self._cancel_flags[task_id] = True

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context.context_id,
                status=TaskStatus(
                    state=TaskState.TASK_STATE_CANCELED,
                    message=Message(
                        role=Role.ROLE_AGENT,
                        parts=[Part(text="取消请求已发送")],
                    ),
                ),
            )
        )

    @staticmethod
    async def _fail(
        event_queue: EventQueue,
        task_id: str,
        context_id: str,
        error: str,
        task_already_created: bool = False,
    ):
        if not task_already_created:
            # 首次事件必须是 Task 对象
            await event_queue.enqueue_event(
                Task(
                    id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.TASK_STATE_FAILED,
                        message=Message(
                            role=Role.ROLE_AGENT,
                            parts=[Part(text=error)],
                        ),
                    ),
                )
            )
        else:
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.TASK_STATE_FAILED,
                        message=Message(
                            role=Role.ROLE_AGENT,
                            parts=[Part(text=error)],
                        ),
                    ),
                )
            )
