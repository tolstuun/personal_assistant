"""
Orchestrator — central task coordinator.

Routes tasks to appropriate handlers and manages execution.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.primitives import FetchResult, fetch

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of task execution."""
    success: bool
    task_type: str
    data: dict[str, Any] | None = None
    error: str | None = None
    executed_at: datetime = field(default_factory=datetime.now)


class Orchestrator:
    """
    Central orchestrator for all tasks.

    Routes incoming tasks to appropriate handlers (primitives or agents).
    Tracks execution statistics.

    Usage:
        orchestrator = Orchestrator()
        result = await orchestrator.execute_task(
            task_type="fetch",
            params={"url": "https://example.com"},
            user_id=123
        )
    """

    def __init__(self):
        self.tasks_processed = 0
        self.started_at = datetime.now()

        # Registry of task handlers
        self._handlers: dict[str, callable] = {
            "fetch": self._handle_fetch,
        }

    async def execute_task(
        self,
        task_type: str,
        params: dict[str, Any],
        user_id: int | None = None
    ) -> dict[str, Any]:
        """
        Execute a task.

        Args:
            task_type: Type of task (e.g., "fetch", "digest")
            params: Task parameters
            user_id: Telegram user ID (for logging/tracking)

        Returns:
            Dict with success status and result/error
        """
        logger.info(f"Executing task: {task_type} for user {user_id}")

        handler = self._handlers.get(task_type)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown task type: {task_type}"
            }

        try:
            result = await handler(params)
            self.tasks_processed += 1

            return {
                "success": True,
                "data": result
            }

        except Exception as e:
            logger.error(f"Task {task_type} failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_status(self) -> dict[str, Any]:
        """Get orchestrator status."""
        uptime = datetime.now() - self.started_at

        return {
            "orchestrator": "running",
            "uptime_seconds": int(uptime.total_seconds()),
            "agents_count": 0,  # No agents yet
            "tasks_processed": self.tasks_processed,
            "available_tasks": list(self._handlers.keys())
        }

    # --- Task Handlers ---

    async def _handle_fetch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle fetch task."""
        url = params.get("url")
        if not url:
            raise ValueError("URL is required")

        result: FetchResult = await fetch(url)

        return {
            "url": result.url,
            "status_code": result.status_code,
            "content_type": result.content_type.value,
            "content_length": result.content_length,
            "elapsed_ms": result.elapsed_ms,
            "ok": result.ok
        }

    def register_handler(self, task_type: str, handler: callable):
        """Register a new task handler."""
        self._handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
