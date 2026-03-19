"""MCP client for connecting to the quiz validation server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from rich.console import Console

console = Console()

# Path to the server module
SERVER_MODULE = "mcp_validator.server"


class ValidatorClient:
    """Connects to the MCP validation server and calls validate_quiz_answer."""

    def __init__(self):
        self._session: ClientSession | None = None
        self._cm = None  # context manager for stdio transport
        self._transport = None

    async def connect(self):
        """Start the MCP server as a subprocess and connect."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", SERVER_MODULE],
            cwd=str(Path(__file__).parent.parent),
        )
        self._cm = stdio_client(server_params)
        read_stream, write_stream = await self._cm.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.initialize()
        console.print("[dim]MCP validator connected[/dim]")

    async def validate(
        self,
        question: str,
        options: list[str],
        proposed_answer: str,
        course_context: str = "Anthropic Academy",
    ) -> dict:
        """Call the validate_quiz_answer tool.

        Returns:
            {
                "validated": bool,
                "confidence": float,
                "reasoning": str,
                "suggested_answer": str | None,
            }
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")

        result = await self._session.call_tool(
            "validate_quiz_answer",
            arguments={
                "question": question,
                "options": options,
                "proposed_answer": proposed_answer,
                "course_context": course_context,
            },
        )

        # Parse the text content response
        if result.content and len(result.content) > 0:
            text = result.content[0].text
            return json.loads(text)

        return {"validated": True, "confidence": 0.5, "reasoning": "No response", "suggested_answer": None}

    async def close(self):
        """Shut down the MCP connection."""
        if self._cm:
            await self._cm.__aexit__(None, None, None)
        self._session = None
        self._cm = None
