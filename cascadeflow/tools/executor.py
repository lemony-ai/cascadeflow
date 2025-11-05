"""
Tool execution engine for cascadeflow.

Executes tool calls and manages results.
"""

import inspect
import logging
from datetime import datetime
from typing import Optional

from .call import ToolCall
from .config import ToolConfig
from .result import ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tool calls and manages results.

    This is the engine that actually runs your tools.
    """

    def __init__(self, tools: list[ToolConfig]):
        """
        Initialize executor with available tools.

        Args:
            tools: List of tool configurations
        """
        self.tools = {tool.name: tool for tool in tools}
        logger.info(
            f"Initialized ToolExecutor with {len(self.tools)} tools: " f"{list(self.tools.keys())}"
        )

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call to execute

        Returns:
            Tool execution result
        """
        start_time = datetime.now()

        # Get the tool
        tool = self.tools.get(tool_call.name)
        if not tool:
            error_msg = (
                f"Tool '{tool_call.name}' not found. " f"Available: {list(self.tools.keys())}"
            )
            logger.error(error_msg)
            return ToolResult(
                call_id=tool_call.id, name=tool_call.name, result=None, error=error_msg
            )

        # Check if tool has executable function
        if not tool.function:
            error_msg = f"Tool '{tool_call.name}' has no executable function"
            logger.error(error_msg)
            return ToolResult(
                call_id=tool_call.id, name=tool_call.name, result=None, error=error_msg
            )

        # Execute the tool
        try:
            logger.info(f"Executing tool '{tool_call.name}' " f"with args: {tool_call.arguments}")

            # Handle both sync and async functions
            if inspect.iscoroutinefunction(tool.function):
                result = await tool.function(**tool_call.arguments)
            else:
                result = tool.function(**tool_call.arguments)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Tool '{tool_call.name}' succeeded " f"in {execution_time:.1f}ms")

            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                result=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"

            logger.error(
                f"Tool '{tool_call.name}' failed " f"after {execution_time:.1f}ms: {error_msg}"
            )

            return ToolResult(
                call_id=tool_call.id,
                name=tool_call.name,
                result=None,
                error=error_msg,
                execution_time_ms=execution_time,
            )

    async def execute_parallel(
        self, tool_calls: list[ToolCall], max_parallel: int = 5
    ) -> list[ToolResult]:
        """
        Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of tool calls to execute
            max_parallel: Maximum number of parallel executions

        Returns:
            List of tool results in same order as tool_calls
        """
        import asyncio

        if not tool_calls:
            return []

        logger.info(f"Executing {len(tool_calls)} tools in parallel " f"(max={max_parallel})")

        # Create semaphore to limit concurrent executions
        semaphore = asyncio.Semaphore(max_parallel)

        async def execute_with_semaphore(call: ToolCall) -> ToolResult:
            async with semaphore:
                return await self.execute(call)

        # Execute all in parallel
        results = await asyncio.gather(*[execute_with_semaphore(call) for call in tool_calls])

        # Log summary
        successful = sum(1 for r in results if r.success)
        logger.info(f"Parallel execution complete: " f"{successful}/{len(results)} succeeded")

        return results

    def get_tool(self, name: str) -> Optional[ToolConfig]:
        """Get tool configuration by name."""
        return self.tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if tool exists."""
        return name in self.tools

    def list_tools(self) -> list[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())
