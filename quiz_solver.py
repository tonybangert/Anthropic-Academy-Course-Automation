"""Quiz detection, extraction, Claude-powered solving, and submission.

Skilljar quizzes display one question at a time via AJAX:
  Start -> Q1 -> answer -> Next -> Q2 -> ... -> Results
"""

from __future__ import annotations

import re

from playwright.async_api import Page
from rich.console import Console

from config import TARGET_SCORE, MAX_QUIZ_RETRIES
from models import QuizQuestion, QuizResult
from claude_client import ask_claude
from mcp_validator.client import ValidatorClient

console = Console()


def _sanitize(text: str) -> str:
    """Replace Unicode characters that break Windows cp1252 terminal."""
    return (
        text
        .replace("\u2192", "->")   # right arrow
        .replace("\u2190", "<-")   # left arrow
        .replace("\u2194", "<->")  # left-right arrow
        .replace("\u2013", "-")    # en dash
        .replace("\u2014", "--")   # em dash
        .replace("\u2018", "'")    # left single quote
        .replace("\u2019", "'")    # right single quote
        .replace("\u201c", '"')    # left double quote
        .replace("\u201d", '"')    # right double quote
        .replace("\u2026", "...")  # ellipsis
        .replace("\u2022", "*")   # bullet
        .replace("\u00b7", "*")   # middle dot
        .replace("\u2713", "[x]") # check mark
        .replace("\u2717", "[ ]") # ballot x
    )


# -- Skilljar quiz selectors (discovered from live DOM) -----------------------

# Start / retake buttons
START_SELECTORS = [
    "button.sj-text-quiz-start",
    "button:has-text('Start')",
    "button:has-text('Retake')",
    "button:has-text('Retry')",
    "a:has-text('Take this again')",
    "a:has-text('Retake')",
    "a:has-text('Retry')",
]

# Question text
QUESTION_TEXT_SEL = "#sj-quiz-question-text"

# Question number (e.g. "Question 1 of 6")
QUESTION_NUMBER_SEL = ".question-number"

# Answer inputs
RADIO_SEL = "input[name='answer']"
CHECKBOX_SEL = "input[name='chosen_answers']"

# Labels wrapping answers
ANSWER_LABEL_SEL = ".form-answers label"

# Next question button
NEXT_Q_SELECTORS = [
    "button.sj-text-quiz-next",
    "button:has-text('Next Question')",
    "button:has-text('Submit')",
    "button:has-text('Finish')",
]

# Results page elements
SCORE_SELECTORS = [
    ".quiz-score",
    ".score",
    ".result-score",
    ".sj-quiz-score",
    ".grade",
]


async def _click_first(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    """Click the first visible element matching any selector."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                await el.click()
                await page.wait_for_timeout(timeout)
                return True
        except Exception:
            continue
    return False


async def _extract_current_question(page: Page) -> QuizQuestion | None:
    """Extract the currently displayed single question and its options."""
    # Get question text
    q_text_el = await page.query_selector(QUESTION_TEXT_SEL)
    if not q_text_el:
        # Fallback: look for .question-text
        q_text_el = await page.query_selector(".question-text")
    if not q_text_el:
        return None

    q_text = _sanitize((await q_text_el.inner_text()).strip())
    if not q_text:
        return None

    # Get question number from "Question X of Y"
    q_num = 1
    total = 1
    num_el = await page.query_selector(QUESTION_NUMBER_SEL)
    if num_el:
        num_text = (await num_el.inner_text()).strip()
        m = re.search(r"(\d+)\s+of\s+(\d+)", num_text)
        if m:
            q_num = int(m.group(1))
            total = int(m.group(2))

    # Get answer options from labels
    options: list[str] = []
    labels = await page.query_selector_all(ANSWER_LABEL_SEL)
    for label in labels:
        text = _sanitize((await label.inner_text()).strip())
        if text:
            options.append(text)

    return QuizQuestion(number=q_num, text=q_text, options=options)


async def _select_answer_on_page(page: Page, answer_text: str) -> bool:
    """Select the radio/checkbox matching the answer text."""
    labels = await page.query_selector_all(ANSWER_LABEL_SEL)
    for label in labels:
        text = _sanitize((await label.inner_text()).strip())
        if text == answer_text or answer_text in text or text in answer_text:
            # Click the input inside the label
            radio = await label.query_selector("input[type='radio'], input[type='checkbox']")
            if radio:
                await radio.click()
                return True
            # Fallback: click the label itself
            await label.click()
            return True

    # Last resort: try partial text match
    for label in labels:
        text = _sanitize((await label.inner_text()).strip())
        # Check if most of the answer text matches
        if len(answer_text) > 10 and answer_text[:30] in text:
            radio = await label.query_selector("input[type='radio'], input[type='checkbox']")
            if radio:
                await radio.click()
                return True
            await label.click()
            return True

    return False


async def _parse_score(page: Page) -> float:
    """Extract the score percentage from the results page."""
    # Check dedicated score elements
    for sel in SCORE_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                pct = re.search(r"(\d+)%", text)
                if pct:
                    return float(pct.group(1))
                frac = re.search(r"(\d+)\s*/\s*(\d+)", text)
                if frac:
                    n, d = int(frac.group(1)), int(frac.group(2))
                    if d > 0:
                        return (n / d) * 100
        except Exception:
            continue

    # Fallback: search quiz container text for percentage or fraction
    quiz_el = await page.query_selector("#quiz-container")
    if quiz_el:
        text = await quiz_el.inner_text()
        pct = re.search(r"(\d+)%", text)
        if pct:
            return float(pct.group(1))
        frac = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if frac:
            n, d = int(frac.group(1)), int(frac.group(2))
            if d > 0:
                return (n / d) * 100

    # Fallback: search full page
    try:
        body = await page.inner_text("body")
        # Look for "Score: 83%" or "5/6" or "83%" patterns
        pct = re.search(r"(\d+)\s*%", body)
        if pct:
            val = float(pct.group(1))
            # Sanity check: should be 0-100 and appear in quiz context
            if 0 < val <= 100:
                return val
    except Exception:
        pass

    return 0.0


async def handle_quiz_lesson(
    page: Page,
    validator: ValidatorClient | None = None,
    course_context: str = "Anthropic Academy",
) -> QuizResult:
    """Full quiz pipeline using Skilljar's one-question-at-a-time flow.

    Flow: Start -> Q1 -> answer -> Next -> Q2 -> ... -> Results
    Retries up to MAX_QUIZ_RETRIES if score < TARGET_SCORE.
    """
    console.print("[bold cyan]    Handling quiz lesson...[/bold cyan]")
    wrong_answers_map: dict[int, list[str]] = {}

    for attempt in range(1, MAX_QUIZ_RETRIES + 1):
        console.print(f"[cyan]    Quiz attempt {attempt}/{MAX_QUIZ_RETRIES}[/cyan]")
        questions_answered: list[QuizQuestion] = []

        # On retries, reload the page to get a clean quiz state
        if attempt > 1:
            await page.reload(wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

        # Click Start or Retake
        started = await _click_first(page, START_SELECTORS, timeout=3000)
        if not started:
            console.print("[yellow]    No Start/Retake button found[/yellow]")
            # Might already be on a question page
            pass

        await page.wait_for_timeout(2000)

        # Answer questions one at a time
        max_questions = 50  # safety limit
        for _ in range(max_questions):
            question = await _extract_current_question(page)
            if not question:
                # No question visible -- might be on results page
                break

            if not question.options:
                console.print(f"[yellow]    Q{question.number}: No options found, advancing[/yellow]")
                await _click_first(page, NEXT_Q_SELECTORS, timeout=2000)
                continue

            # Ask Claude for the answer
            # On retries, use higher temperature for variation
            temp = 0.0 if attempt == 1 else 0.4
            wrong = wrong_answers_map.get(question.number, [])
            answer = ask_claude(
                question,
                wrong_answers=wrong if wrong else None,
                temperature=temp,
                course_context=course_context,
            )

            # Optional MCP validation
            if validator:
                answer = await _validate_with_mcp(
                    validator, question, answer, course_context
                )

            question.selected_answer = answer
            console.print(f"[dim]    Q{question.number}: {question.text[:60]}[/dim]")
            console.print(f"[dim]    -> {answer[:60]}[/dim]")

            # Simulate reading time (10-20 seconds per question)
            import random
            delay = random.uniform(10, 20)
            console.print(f"[dim]    (waiting {delay:.0f}s)[/dim]")
            await page.wait_for_timeout(int(delay * 1000))

            # Select the answer in the browser
            selected = await _select_answer_on_page(page, answer)
            if not selected:
                console.print(f"[yellow]    Could not select answer for Q{question.number}[/yellow]")

            questions_answered.append(question)

            # Small pause before clicking Next
            await page.wait_for_timeout(random.randint(2000, 4000))

            # Click Next Question (or Submit/Finish for last question)
            clicked = await _click_first(page, NEXT_Q_SELECTORS, timeout=3000)
            if not clicked:
                console.print("[dim]    No Next button -- may be end of quiz[/dim]")
                break

        # We should now be on the results page
        await page.wait_for_timeout(3000)

        # Parse score
        score = await _parse_score(page)
        passed = score >= TARGET_SCORE

        result = QuizResult(
            score_percent=score,
            passed=passed,
            questions=questions_answered,
            attempt_number=attempt,
        )

        status_color = "green" if passed else "yellow"
        console.print(
            f"[{status_color}]    Score: {score:.0f}% "
            f"({'PASS' if passed else 'RETRY'})"
            f"[/{status_color}]"
        )

        if passed:
            return result

        # On failure, conservatively record all answers as potentially wrong
        # (Skilljar results page may or may not show which were wrong)
        await _record_wrong_answers(page, questions_answered, wrong_answers_map)

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
    """Run the proposed answer through the MCP validator."""
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
                f"[yellow]    MCP: rejected ({confidence:.0%}) -- {reasoning[:80]}[/yellow]"
            )
            if suggested and suggested in question.options:
                console.print(f"[cyan]    MCP: using alternative -> {suggested[:60]}[/cyan]")
                return suggested
            else:
                console.print("[dim]    MCP: no valid alternative, keeping original[/dim]")
                return proposed_answer

    except Exception as e:
        console.print(f"[yellow]    MCP validation error: {e} -- using original answer[/yellow]")
        return proposed_answer


async def _record_wrong_answers(
    page: Page,
    questions: list[QuizQuestion],
    wrong_answers_map: dict[int, list[str]],
):
    """After quiz results, try to identify which specific answers were wrong.

    If we can't identify individual wrong answers (Skilljar may not show
    detailed results), we skip recording to avoid poisoning correct answers.
    The retry relies on temperature variation instead.
    """
    # Try clicking "Show Answers" to get detailed results
    show_btn = await page.query_selector("button:has-text('Show Answers')")
    if show_btn:
        try:
            await show_btn.click()
            await page.wait_for_timeout(3000)

            # Look for incorrect markers in the results
            incorrect_els = await page.query_selector_all(
                ".incorrect, .is-incorrect, .wrong, [data-correct='false'], "
                ".answer-incorrect, .sj-incorrect"
            )
            if incorrect_els:
                console.print(f"[dim]    Found {len(incorrect_els)} incorrect markers[/dim]")
                # TODO: map these back to specific questions
            else:
                console.print("[dim]    No specific wrong-answer markers found[/dim]")
        except Exception:
            pass

    # Without clear per-question markers, don't exclude anything.
    # Retry relies on temperature variation to explore alternatives.
    console.print("[dim]    Using temperature variation for retry (no answer exclusions)[/dim]")
