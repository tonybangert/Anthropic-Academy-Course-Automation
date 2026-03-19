"""MCP server that validates quiz answers via a second Claude reviewer call.

Run standalone:  python -m mcp_validator.server
The bot connects to it over stdio transport.
"""

from __future__ import annotations

import json
import os
import sys

import anthropic
from mcp.server import Server
from mcp.server.stdio import run_stdio
from mcp.types import Tool, TextContent

# ── Config ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "claude-sonnet-4-20250514")
CONFIDENCE_THRESHOLD = 0.85  # below this, suggest an alternative

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
server = Server("quiz-validator")


# ── Tool definition ───────────────────────────────────────────────
VALIDATE_TOOL = Tool(
    name="validate_quiz_answer",
    description=(
        "Validates a proposed quiz answer using chain-of-thought review. "
        "Returns a confidence score and, if confidence is low, an alternative answer."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The quiz question text",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of answer options",
            },
            "proposed_answer": {
                "type": "string",
                "description": "The answer selected by the primary solver",
            },
            "course_context": {
                "type": "string",
                "description": "Which course this question is from (e.g. 'Claude API', 'MCP')",
            },
        },
        "required": ["question", "options", "proposed_answer"],
    },
)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [VALIDATE_TOOL]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "validate_quiz_answer":
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    result = validate_answer(
        question=arguments["question"],
        options=arguments["options"],
        proposed_answer=arguments["proposed_answer"],
        course_context=arguments.get("course_context", "Anthropic Academy"),
    )
    return [TextContent(type="text", text=json.dumps(result))]


# ── Core validation logic ─────────────────────────────────────────
def validate_answer(
    question: str,
    options: list[str],
    proposed_answer: str,
    course_context: str = "Anthropic Academy",
) -> dict:
    """Ask a reviewer model to validate the proposed answer.

    Returns:
        {
            "validated": bool,
            "confidence": float (0-1),
            "reasoning": str,
            "suggested_answer": str | null  (only if validated=False)
        }
    """
    options_block = "\n".join(f"  {chr(65+i)}) {opt}" for i, opt in enumerate(options))

    prompt = (
        f"You are a quiz answer reviewer for {course_context} courses "
        f"(covering Claude API, MCP, agentic patterns, Claude Code).\n\n"
        f"A primary solver chose an answer. Your job: independently determine "
        f"the correct answer, then evaluate whether the proposed answer is right.\n\n"
        f"Question: {question}\n\n"
        f"Options:\n{options_block}\n\n"
        f"Proposed answer: {proposed_answer}\n\n"
        f"Think step by step:\n"
        f"1. What is this question really asking?\n"
        f"2. Evaluate each option against your knowledge.\n"
        f"3. Which option is correct and why?\n"
        f"4. Does the proposed answer match?\n\n"
        f"Respond in this exact JSON format:\n"
        f'{{"correct_answer": "<exact option text>", '
        f'"confidence": <0.0-1.0>, '
        f'"reasoning": "<brief explanation>", '
        f'"agrees_with_proposed": <true/false>}}'
    )

    try:
        response = client.messages.create(
            model=REVIEWER_MODEL,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)

        confidence = float(parsed.get("confidence", 0.5))
        agrees = parsed.get("agrees_with_proposed", True)
        correct = parsed.get("correct_answer", proposed_answer)
        reasoning = parsed.get("reasoning", "")

        if agrees and confidence >= CONFIDENCE_THRESHOLD:
            return {
                "validated": True,
                "confidence": confidence,
                "reasoning": reasoning,
                "suggested_answer": None,
            }
        else:
            # Reviewer disagrees or low confidence — suggest the reviewer's pick
            suggested = _match_to_option(correct, options)
            return {
                "validated": False,
                "confidence": confidence,
                "reasoning": reasoning,
                "suggested_answer": suggested if suggested != proposed_answer else None,
            }

    except (json.JSONDecodeError, KeyError) as e:
        # If parsing fails, pass through with medium confidence
        return {
            "validated": True,
            "confidence": 0.6,
            "reasoning": f"Reviewer response parsing failed: {e}",
            "suggested_answer": None,
        }
    except anthropic.APIError as e:
        return {
            "validated": True,
            "confidence": 0.5,
            "reasoning": f"Reviewer API error: {e}",
            "suggested_answer": None,
        }


def _match_to_option(text: str, options: list[str]) -> str:
    """Best-effort match of reviewer's answer text to an exact option."""
    text_lower = text.lower().strip()
    for opt in options:
        if opt.lower().strip() == text_lower:
            return opt
        if text_lower in opt.lower() or opt.lower() in text_lower:
            return opt
    return text


# ── Entry point ───────────────────────────────────────────────────
async def main():
    await run_stdio(server)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
