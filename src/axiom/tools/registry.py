from typing import Any, Callable
from pydantic import BaseModel
import time
import logging

logger = logging.getLogger(__name__)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: int = 0


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, parameters: dict[str, Any], handler: Callable):
        self._tools[name] = ToolDefinition(name=name, description=description, parameters=parameters, handler=handler)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
        ]

    async def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        start = time.time()
        try:
            result = await tool.handler(**kwargs)
            duration = int((time.time() - start) * 1000)
            logger.info(f"Tool {name} executed in {duration}ms")
            return ToolResult(success=True, data=result, duration_ms=duration)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            logger.error(f"Tool {name} failed: {e}")
            return ToolResult(success=False, error=str(e), duration_ms=duration)


registry = ToolRegistry()
