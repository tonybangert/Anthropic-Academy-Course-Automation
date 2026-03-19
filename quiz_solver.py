"""Quiz detection, extraction, Claude-powered solving, and submission."""

from __future__ import annotations

import re

from playwright.async_api import Page
from rich.console import Console

from config import TARGET_SCORE, MAX_QUIZ_RETRIES
from models import QuizQuestion, QuizResult
from claude_client import ask_claude
from mcp_validator.client import ValidatorClient
from selectors import (
    QUIZ_CONTAINER_CANDIDATES,
    QUIZ_START_BUTTON_CANDIDATES,
    QUIZ_QUESTION_CANDIDATES,
    QUIZ_QUESTION_TEXT_CANDIDATES,
    QUIZ_OPTION_CANDIDATES,
    QUIZ_RADIO_CANDIDATES,
    QUIZ_SUBMIT_CANDIDATES,
    QUIZ_SCORE_CANDIDATES,
    QUIZ_RESULT_CONTAINER_CANDIDATES,
    QUIZ_CORRECT_INDICATOR,
    QUIZ_INCORRECT_INDICATOR,
)

console = Console()


async def _find_first(page, candidates: list[str]):
    """Return first matching element and its selector."""
    for sel in candidates:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return el, sel
        except Exception:
            continue
    return None, None


async def _find_all_matching(page, candidates: list[str]):
    """Return all elements matching the first working candidate selector."""
    for sel in candidates:
        try:
            els = await page.query_selector_all(sel)
            visible = []
            for el in els:
                try:
                    if await el.is_visible():
                        visible.append(el)
                except Exception:
                    visible.append(el)
            if visible:
                return visible, sel
        except Exception:
            continue
    return [], None


async def _click_start_quiz(page: Page) -> bool:
    """Find and click the Start/Retake Quiz button."""
    el, sel = await _find_first(page, QUIZ_START_BUTTON_CANDIDATES)
    if el:
        console.print(f"[dim]    Clicking start: {sel}[/dim]")
        await el.click()
        await page.wait_for_timeout(3000)
        return True
    return False


async def _extract_questions(page: Page) -> list[QuizQuestion]:
    """Extract all quiz questions and their options from the page."""
    questions: list[QuizQuestion] = []

    # Find question containers
    q_elements, q_sel = await _find_all_matching(page, QUIZ_QUESTION_CANDIDATES)

    if not q_elements:
        console.print("[yellow]    No question containers found, trying full-page extraction[/yellow]")
        return await _extract_questions_fullpage(page)

    console.print(f"[dim]    Found {len(q_elements)} questions via {q_sel}[/dim]")

    for i, q_el in enumerate(q_elements):
        # Extract question text
        q_text = ""
        for text_sel in QUIZ_QUESTION_TEXT_CANDIDATES:
            try:
                text_el = await q_el.query_selector(text_sel)
                if text_el:
                    q_text = (await text_el.inner_text()).strip()
                    if q_text:
                        break
            except Exception:
                continue

        if not q_text:
            q_text = (await q_el.inner_text()).strip()
            # Take first meaningful line as question
            lines = [l.strip() for l in q_text.split("\n") if l.strip()]
            q_text = lines[0] if lines else f"Question {i + 1}"

        # Extract options
        options: list[str] = []
        option_els, _ = await _find_all_matching(q_el, QUIZ_OPTION_CANDIDATES)
        for opt_el in option_els:
            opt_text = (await opt_el.inner_text()).strip()
            # Clean up option text (remove leading A), B), etc.)
            opt_text = re.sub(r"^[A-Z][.)]\s*", "", opt_text)
            if opt_text and opt_text != q_text:
                options.append(opt_text)

        questions.append(
            QuizQuestion(number=i + 1, text=q_text, options=options)
        )

    return questions


async def _extract_questions_fullpage(page: Page) -> list[QuizQuestion]:
    """Fallback: extract questions from full page text structure."""
    # Get all text content and try to parse question/answer patterns
    body = await page.inner_text("body")
    questions = []
    # Look for numbered patterns like "1. Question text" or "Question 1:"
    q_pattern = re.compile(r"(?:^|\n)\s*(?:Question\s+)?(\d+)[.):]\s*(.+?)(?=\n)", re.MULTILINE)
    for match in q_pattern.finditer(body):
        num = int(match.group(1))
        text = match.group(2).strip()
        if text:
            questions.append(QuizQuestion(number=num, text=text, options=[]))

    return questions


async def _select_answer(page: Page, question_el, answer_text: str) -> bool:
    """Select a radio button corresponding to the answer text."""
    # Find all label/option elements
    option_els, _ = await _find_all_matching(question_el, QUIZ_OPTION_CANDIDATES)

    for opt_el in option_els:
        opt_text = (await opt_el.inner_text()).strip()
        cleaned = re.sub(r"^[A-Z][.)]\s*", "", opt_text)
        if cleaned == answer_text or answer_text in opt_text:
            # Try clicking the radio input inside the option
            radio = await opt_el.query_selector("input[type='radio'], input[type='checkbox']")
            if radio:
                await radio.click()
                return True
            # Fallback: click the label/option element itself
            await opt_el.click()
            return True

    # Last resort: try clicking by text match
    try:
        label = await page.query_selector(f"label:has-text('{answer_text[:50]}')")
        if label:
            await label.click()
            return True
    except Exception:
        pass

    return False


async def _submit_quiz(page: Page) -> bool:
    """Click the submit button."""
    el, sel = await _find_first(page, QUIZ_SUBMIT_CANDIDATES)
    if el:
        console.print(f"[dim]    Submitting quiz via {sel}[/dim]")
        await el.click()
        await page.wait_for_timeout(5000)
        return True
    return False


async def _parse_results(page: Page) -> QuizResult:
    """Parse quiz results after submission."""
    # Try to find score
    score = 0.0
    for sel in QUIZ_SCORE_CANDIDATES:
        try:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                # Extract percentage from text like "Score: 80%" or "4/5"
                pct_match = re.search(r"(\d+)%", text)
                if pct_match:
                    score = float(pct_match.group(1))
                    break
                frac_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
                if frac_match:
                    num, den = int(frac_match.group(1)), int(frac_match.group(2))
                    if den > 0:
                        score = (num / den) * 100
                    break
        except Exception:
            continue

    # If no explicit score element, look in page text
    if score == 0:
        try:
            body = await page.inner_text("body")
            pct_match = re.search(r"(\d+)%", body)
            if pct_match:
                score = float(pct_match.group(1))
        except Exception:
            pass

    passed = score >= TARGET_SCORE
    return QuizResult(score_percent=score, passed=passed)


async def handle_quiz_lesson(
    page: Page,
    validator: ValidatorClient | None = None,
    course_context: str = "Anthropic Academy",
) -> QuizResult:
    """Full quiz pipeline: start → extract → solve → validate → submit → check.

    Retries up to MAX_QUIZ_RETRIES times if score < TARGET_SCORE.
    """
    console.print("[bold cyan]    Handling quiz lesson...[/bold cyan]")
    wrong_answers_map: dict[int, list[str]] = {}  # question_num -> wrong answers

    for attempt in range(1, MAX_QUIZ_RETRIES + 1):
        console.print(f"[cyan]    Quiz attempt {attempt}/{MAX_QUIZ_RETRIES}[/cyan]")

        # Start or retake quiz
        await _click_start_quiz(page)
        await page.wait_for_timeout(2000)

        # Extract questions
        questions = await _extract_questions(page)
        if not questions:
            console.print("[red]    No questions found![/red]")
            return QuizResult(score_percent=0, passed=False, attempt_number=attempt)

        console.print(f"[cyan]    Found {len(questions)} questions[/cyan]")

        # Find question elements for interaction
        q_elements, _ = await _find_all_matching(page, QUIZ_QUESTION_CANDIDATES)

        # Answer each question
        for i, q in enumerate(questions):
            if not q.options:
                console.print(f"[yellow]    Q{q.number}: No options found, skipping[/yellow]")
                continue

            wrong = wrong_answers_map.get(q.number, [])
            answer = ask_claude(q, wrong_answers=wrong if wrong else None)

            # MCP validation gate — verify answer before selecting
            if validator:
                answer = await _validate_with_mcp(
                    validator, q, answer, course_context
                )

            q.selected_answer = answer

            console.print(f"[dim]    Q{q.number}: {q.text[:60]}...[/dim]")
            console.print(f"[dim]    → Answer: {answer[:60]}[/dim]")

            # Select the answer in the browser
            if i < len(q_elements):
                selected = await _select_answer(page, q_elements[i], answer)
                if not selected:
                    console.print(f"[yellow]    Could not select answer for Q{q.number}[/yellow]")

        # Submit
        submitted = await _submit_quiz(page)
        if not submitted:
            console.print("[yellow]    Could not find submit button[/yellow]")

        # Parse results
        result = await _parse_results(page)
        result.questions = questions
        result.attempt_number = attempt

        console.print(
            f"[{'green' if result.passed else 'yellow'}]"
            f"    Score: {result.score_percent:.0f}% "
            f"({'PASS' if result.passed else 'RETRY'})"
            f"[/{'green' if result.passed else 'yellow'}]"
        )

        if result.passed:
            return result

        # Track wrong answers for retry by inspecting result DOM
        await _tag_wrong_answers(page, questions, q_elements, wrong_answers_map)

        await page.wait_for_timeout(2000)

    console.print("[red]    Max quiz retries reached[/red]")
    return QuizResult(
        score_percent=0, passed=False, attempt_number=MAX_QUIZ_RETRIES
    )


async def _validate_with_mcp(
    validator: ValidatorClient,
    question: QuizQuestion,
    proposed_answer: str,
    course_context: str,
) -> str:
    """Run the proposed answer through the MCP validator.

    Returns the final answer — either the original or the reviewer's alternative.
    """
    try:
        result = await validator.validate(
            question=question.text,
            options=question.options,
            proposed_answer=proposed_answer,
            course_context=course_context,
        )

        confidence = result.get("confidence", 1.0)
        validated = result.get("validated", True)
        reasoning = result.get("reasoning", "")
        suggested = result.get("suggested_answer")

        if validated:
            console.print(
                f"[dim]    MCP: validated ({confidence:.0%} confidence)[/dim]"
            )
            return proposed_answer
        else:
            console.print(
                f"[yellow]    MCP: rejected ({confidence:.0%}) — {reasoning[:80]}[/yellow]"
            )
            if suggested and suggested in question.options:
                console.print(f"[cyan]    MCP: using alternative → {suggested[:60]}[/cyan]")
                return suggested
            else:
                console.print("[dim]    MCP: no valid alternative, keeping original[/dim]")
                return proposed_answer

    except Exception as e:
        console.print(f"[yellow]    MCP validation error: {e} — using original answer[/yellow]")
        return proposed_answer


async def _tag_wrong_answers(
    page: Page,
    questions: list[QuizQuestion],
    q_elements: list,
    wrong_answers_map: dict[int, list[str]],
):
    """After submission, inspect the DOM to find which answers were wrong.

    If the platform marks correct/incorrect answers, we only record the
    genuinely wrong ones. Otherwise, we conservatively record all selected
    answers (the retry prompt will exclude them).
    """
    found_any_marker = False

    for i, q in enumerate(questions):
        if i >= len(q_elements):
            break

        q_el = q_elements[i]
        is_wrong = False

        # Check for explicit incorrect markers on the question container
        for indicator in QUIZ_INCORRECT_INDICATOR:
            try:
                marker = await q_el.query_selector(indicator)
                if marker:
                    is_wrong = True
                    found_any_marker = True
                    break
            except Exception:
                continue

        # Also check for correct markers — if present and NOT found, it's wrong
        if not found_any_marker:
            for indicator in QUIZ_CORRECT_INDICATOR:
                try:
                    marker = await q_el.query_selector(indicator)
                    if marker:
                        q.is_correct = True
                        found_any_marker = True
                        break
                except Exception:
                    continue
            if found_any_marker and q.is_correct is None:
                is_wrong = True

        if is_wrong and q.selected_answer:
            q.is_correct = False
            wrong_answers_map.setdefault(q.number, []).append(q.selected_answer)
            console.print(f"[dim]    Q{q.number}: '{q.selected_answer}' was wrong[/dim]")

    # If no DOM markers were found at all, conservatively mark all as potentially wrong
    if not found_any_marker:
        console.print("[dim]    No correct/incorrect markers found — recording all answers for retry[/dim]")
        for q in questions:
            if q.selected_answer:
                wrong_answers_map.setdefault(q.number, []).append(q.selected_answer)
