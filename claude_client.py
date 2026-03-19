"""Anthropic SDK wrapper for answering quiz questions."""

from __future__ import annotations

import anthropic
from rich.console import Console

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from models import QuizQuestion

console = Console()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_quiz_prompt(
    question: QuizQuestion,
    wrong_answers: list[str] | None = None,
) -> str:
    """Build the prompt for Claude to answer a multiple-choice question.

    TODO(human): Implement this function. See the Learn by Doing request below.
    """
    pass


def ask_claude(question: QuizQuestion, wrong_answers: list[str] | None = None) -> str:
    """Send a quiz question to Claude and return the selected option text.

    Args:
        question: The quiz question with its options.
        wrong_answers: Previously attempted answers that were wrong (for retries).

    Returns:
        The exact text of the chosen option from question.options.
    """
    prompt = build_quiz_prompt(question, wrong_answers)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=50,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_answer = response.content[0].text.strip()
    return _match_to_option(raw_answer, question.options)


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
    console.print(f"[yellow]    Warning: Could not match '{raw_answer}' to options[/yellow]")
    return options[0] if options else raw_answer
