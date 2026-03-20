"""Anthropic SDK wrapper for answering quiz questions."""

from __future__ import annotations

import time

import anthropic
from rich.console import Console

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from models import QuizQuestion

console = Console()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 2  # seconds


def build_quiz_prompt(
    question: QuizQuestion,
    wrong_answers: list[str] | None = None,
    course_context: str = "",
) -> str:
    """Build the prompt for Claude to answer a multiple-choice question."""
    options_block = "\n".join(
        f"  {chr(65 + i)}) {opt}" for i, opt in enumerate(question.options)
    )

    context_line = ""
    if course_context:
        context_line = f"Course/section context: {course_context}\n\n"

    prompt = (
        "You are an expert on Claude, Anthropic's AI assistant. "
        "You are answering a multiple-choice quiz from Anthropic Academy.\n\n"
        "Key topics and correct patterns from the course:\n"
        "- Claude API: messages, tools, streaming, temperature, system prompts\n"
        "- Prompt engineering: clarity, specificity, XML tags, examples\n"
        "- Prompt evaluation: test datasets, model grading, code grading\n"
        "- Tool use: schemas, multi-turn, batch tools, built-in tools\n"
        "- RAG: chunking, embeddings, BM25, multi-index pipelines\n"
        "- Features: extended thinking, vision, PDF, citations, caching, code execution\n"
        "- MCP: servers expose tools/resources/prompts, clients connect to servers, stdio transport\n"
        "- Workflow patterns:\n"
        "  * Parallelization: split INDEPENDENT sub-tasks and run simultaneously\n"
        "  * Chaining: sequential steps, each building on the previous\n"
        "  * Routing: classify input then send to specialized handler\n"
        "  * Evaluator-Optimizer: generate then evaluate in a loop\n"
        "- Agents: autonomous tool use for open-ended tasks; prefer workflows when steps are known\n"
        "- When evaluating multiple items against criteria, use PARALLELIZATION\n"
        "- When steps are predetermined and predictable, use WORKFLOWS not agents\n\n"
        f"{context_line}"
        f"Question: {question.text}\n\n"
        f"Options:\n{options_block}\n\n"
    )

    if wrong_answers:
        eliminated = ", ".join(f'"{a}"' for a in wrong_answers)
        prompt += (
            f"IMPORTANT: The following answers were already tried and are WRONG -- "
            f"do NOT pick them: {eliminated}\n\n"
        )

    prompt += "Reply with ONLY the letter (A, B, C, D, etc.). Nothing else."
    return prompt


def ask_claude(
    question: QuizQuestion,
    wrong_answers: list[str] | None = None,
    temperature: float = 0.0,
    course_context: str = "",
) -> str:
    """Send a quiz question to Claude and return the selected option text.

    Args:
        question: The quiz question with its options.
        wrong_answers: Previously attempted answers that were wrong (for retries).
        temperature: Sampling temperature (0 = deterministic, higher = more varied).
        course_context: Course/section name for additional context.

    Returns:
        The exact text of the chosen option from question.options.
    """
    prompt = build_quiz_prompt(question, wrong_answers, course_context=course_context)

    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=10,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_answer = response.content[0].text.strip()
            return _extract_answer(raw_answer, question.options)
        except anthropic.APIError as e:
            console.print(f"[yellow]    API error (attempt {attempt}): {e}[/yellow]")
            if attempt < API_RETRY_ATTEMPTS:
                time.sleep(API_RETRY_DELAY * attempt)
            else:
                raise


def _extract_answer(raw_answer: str, options: list[str]) -> str:
    """Extract the answer letter from Claude's response (may include reasoning)."""
    import re

    # Strategy 1: Look for letter patterns in the last few lines
    lines = [l.strip() for l in raw_answer.strip().split("\n") if l.strip()]
    for line in reversed(lines[-5:]):
        # Strip markdown bold
        clean = line.replace("**", "").replace("*", "").strip()
        # Match: bare letter, "A)", "A.", "Answer: A", "The answer is A"
        m = re.search(r"(?:answer[\s:is]*|^)\(?([A-Z])\)?[.)\s]*$", clean, re.IGNORECASE)
        if m:
            letter = m.group(1).upper()
            idx = ord(letter) - ord("A")
            if 0 <= idx < len(options):
                return options[idx]
        # Bare letter (possibly with punctuation)
        if len(clean) <= 4:
            letter_m = re.match(r"^([A-Z])[.):\s]*$", clean, re.IGNORECASE)
            if letter_m:
                idx = ord(letter_m.group(1).upper()) - ord("A")
                if 0 <= idx < len(options):
                    return options[idx]

    # Strategy 2: Search full text for "answer is X" pattern
    m = re.search(r"(?:answer|choice)\s+(?:is|:)\s*\(?([A-Z])\)?", raw_answer, re.IGNORECASE)
    if m:
        idx = ord(m.group(1).upper()) - ord("A")
        if 0 <= idx < len(options):
            return options[idx]

    # Strategy 3: Fall back to the original matching on last line
    last_line = lines[-1] if lines else raw_answer
    return _match_to_option(last_line, options)


def _match_to_option(raw_answer: str, options: list[str]) -> str:
    """Map Claude's response back to an exact option text.

    Claude should respond with just a letter (A, B, C, D), but we handle
    various formats: 'A', 'A)', 'A.', 'Option A', or even the full text.
    """
    # Try direct letter match first
    letter = raw_answer.strip().upper().rstrip(").:")
    if letter and len(letter) == 1 and letter.isalpha():
        idx = ord(letter) - ord("A")
        if 0 <= idx < len(options):
            return options[idx]

    # Try matching against option text (fuzzy)
    raw_lower = raw_answer.lower().strip()
    for opt in options:
        if opt.lower().strip() == raw_lower:
            return opt
        if opt.lower().strip() in raw_lower:
            return opt

    # Last resort: return first option
    safe = raw_answer.encode("ascii", errors="replace").decode("ascii")[:80]
    console.print(f"[yellow]    Warning: Could not match '{safe}' to options[/yellow]")
    return options[0] if options else raw_answer
