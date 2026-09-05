from __future__ import annotations

from collections.abc import Awaitable, Callable

from aeromind.schemas.domain import ExecutionStatus, ToolRequest, ToolResult

ToolHandler = Callable[[dict[str, object]], Awaitable[ToolResult]]


class ToolRegistry:
    """Explicit tool allowlist; arbitrary callable or shell execution is impossible here."""

    def __init__(self, allowed_tools: set[str] | None = None) -> None:
        self._allowed_tools = allowed_tools or {
            "get_drone_status",
            "get_weather",
            "calculate_distance",
            "dispatch_drone",
            "return_to_home",
            "capture_image",
            "raise_alert",
        }
        self._handlers: dict[str, ToolHandler] = {}

    @property
    def allowed_tools(self) -> frozenset[str]:
        return frozenset(self._allowed_tools)

    def register(self, tool_name: str, handler: ToolHandler) -> None:
        if tool_name not in self._allowed_tools:
            raise ValueError(f"Tool is not allowlisted: {tool_name}")
        self._handlers[tool_name] = handler

    async def execute(self, request: ToolRequest) -> ToolResult:
        if request.tool_name not in self._allowed_tools:
            return ToolResult(
                status=ExecutionStatus.BLOCKED,
                tool_name=request.tool_name,
                message="Tool is not allowlisted",
            )
        handler = self._handlers.get(request.tool_name)
        if handler is None:
            return ToolResult(
                status=ExecutionStatus.BLOCKED,
                tool_name=request.tool_name,
                message="Tool is allowlisted but not implemented",
            )
        return await handler(request.arguments)
