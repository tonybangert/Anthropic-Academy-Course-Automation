"""Dispatcher: routes lessons to the appropriate handler by type."""

from __future__ import annotations

from playwright.async_api import Page
from rich.console import Console

from models import Lesson, LessonType, QuizResult
from content_handler import handle_content_lesson
from video_handler import handle_video_lesson
from quiz_solver import handle_quiz_lesson
from mcp_validator.client import ValidatorClient

console = Console()


async def handle_lesson(
    page: Page,
    lesson: Lesson,
    lesson_type: LessonType,
    validator: ValidatorClient | None = None,
    course_context: str = "Anthropic Academy",
) -> dict:
    """Dispatch to the right handler based on lesson type.

    Returns a dict with:
        - type: LessonType value
        - text: extracted text content (for notes)
        - quiz_result: QuizResult (only for quiz lessons)
    """
    result = {"type": lesson_type.value, "text": "", "quiz_result": None}

    if lesson_type == LessonType.QUIZ:
        console.print(f"[bold magenta]  📝 Quiz: {lesson.title}[/bold magenta]")
        quiz_result: QuizResult = await handle_quiz_lesson(
            page, validator=validator, course_context=course_context
        )
        result["quiz_result"] = quiz_result
        # Build notes text from quiz Q&A
        lines = [f"Quiz: {lesson.title}"]
        for q in quiz_result.questions:
            lines.append(f"  Q{q.number}: {q.text}")
            for opt in q.options:
                marker = "→" if opt == q.selected_answer else " "
                lines.append(f"    {marker} {opt}")
            if q.selected_answer:
                lines.append(f"  Answer: {q.selected_answer}")
        lines.append(f"  Score: {quiz_result.score_percent:.0f}%")
        result["text"] = "\n".join(lines)

    elif lesson_type == LessonType.VIDEO:
        console.print(f"[bold blue]  🎬 Video: {lesson.title}[/bold blue]")
        text = await handle_video_lesson(page)
        result["text"] = text or f"Video lesson: {lesson.title}"

    elif lesson_type in (LessonType.TEXT, LessonType.MODULAR, LessonType.PDF):
        console.print(f"[bold green]  📄 Content: {lesson.title}[/bold green]")
        text = await handle_content_lesson(page)
        result["text"] = text

    else:
        console.print(f"[yellow]  ❓ Unknown type: {lesson.title}[/yellow]")
        text = await handle_content_lesson(page)
        result["text"] = text

    return result
