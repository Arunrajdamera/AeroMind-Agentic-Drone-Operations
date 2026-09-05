import pytest

from aeromind.schemas.domain import ExecutionStatus, ToolRequest, ToolResult
from aeromind.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_tool_registry_blocks_unknown_tools() -> None:
    result = await ToolRegistry().execute(ToolRequest(tool_name="arbitrary_execution"))

    assert result.status == ExecutionStatus.BLOCKED


def test_tool_registry_rejects_non_allowlisted_registration() -> None:
    registry = ToolRegistry()

    async def handler(arguments: dict[str, object]) -> ToolResult:
        return ToolResult(status=ExecutionStatus.SUCCEEDED, tool_name="bad_tool", message="bad")

    with pytest.raises(ValueError, match="not allowlisted"):
        registry.register("bad_tool", handler)
