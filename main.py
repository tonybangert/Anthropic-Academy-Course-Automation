"""CLI entry point: orchestrates course automation and notes generation."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

from config import COURSES, COURSE_NOTES_PATH, TARGET_SCORE
from browser import BrowserManager
from navigator import CourseNavigator
from lesson_handler import handle_lesson
from mcp_validator.client import ValidatorClient
from models import LessonStatus, LessonType
from progress import show_banner, show_course_table, show_curriculum, show_quiz_result, create_progress

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Anthropic Academy Course Automator"
    )
    parser.add_argument(
        "--course",
        choices=list(COURSES.keys()),
        help="Run a specific course (default: all)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Launch browser and test selectors — no course actions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse curriculum only, don't process lessons",
    )
    parser.add_argument(
        "--notes-only",
        action="store_true",
        help="Generate notes from already-completed courses",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (not recommended for first run)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip MCP validation of quiz answers (faster but less accurate)",
    )
    return parser.parse_args()


class NotesWriter:
    """Incrementally writes course notes to markdown."""

    def __init__(self, path: Path):
        self.path = path
        self._started = False

    def _ensure_header(self):
        if not self._started:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(f"# Anthropic Academy — Course Notes\n\n")
                f.write(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n")
                f.write("---\n\n")
            self._started = True

    def start_course(self, course_name: str):
        self._ensure_header()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"## {course_name}\n\n")

    def start_section(self, section_name: str):
        if section_name:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"### {section_name}\n\n")

    def add_lesson(self, title: str, lesson_type: str, content: str):
        with open(self.path, "a", encoding="utf-8") as f:
            type_emoji = {"video": "🎬", "quiz": "📝", "text": "📄"}.get(lesson_type, "📌")
            f.write(f"#### {type_emoji} {title}\n\n")
            if content:
                # Truncate very long content but keep it meaningful
                if len(content) > 3000:
                    content = content[:3000] + "\n\n_(content truncated)_"
                f.write(f"{content}\n\n")
            f.write("---\n\n")

    def add_quiz_result(self, title: str, questions: list, score: float):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"#### 📝 {title} (Score: {score:.0f}%)\n\n")
            for q in questions:
                f.write(f"**Q{q.number}:** {q.text}\n")
                for opt in q.options:
                    marker = "**→**" if opt == q.selected_answer else "  "
                    f.write(f"- {marker} {opt}\n")
                if q.selected_answer:
                    f.write(f"\n_Selected: {q.selected_answer}_\n\n")
            f.write("---\n\n")


async def run_discover(browser: BrowserManager):
    """Discovery mode: test login and selectors."""
    page = await browser.launch()
    logged_in = await browser.ensure_logged_in()
    if not logged_in:
        return

    console.print("[green]Login verified. Browser is ready.[/green]")
    console.print("[cyan]You can now inspect the page. Press Ctrl+C to exit.[/cyan]")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass


async def run_course(
    browser: BrowserManager,
    course_key: str,
    notes: NotesWriter,
    dry_run: bool = False,
    validator: ValidatorClient | None = None,
):
    """Process a single course end-to-end."""
    page = browser.page
    nav = CourseNavigator(page)

    # Load course and parse curriculum
    course = await nav.load_course(course_key)
    show_curriculum(course)
    notes.start_course(course.name)

    if dry_run:
        console.print("[yellow]Dry run — skipping lesson processing.[/yellow]")
        return

    # Process each lesson
    current_section = ""
    completed = sum(1 for l in course.lessons if l.status == LessonStatus.COMPLETED)
    total = len(course.lessons)

    with create_progress() as progress:
        task_id = progress.add_task(
            f"[cyan]{course.name}", total=total, completed=completed
        )

        for lesson in course.lessons:
            # Track sections for notes
            if lesson.section and lesson.section != current_section:
                current_section = lesson.section
                notes.start_section(current_section)

            # Skip completed lessons
            if lesson.status == LessonStatus.COMPLETED:
                console.print(f"[dim]  ✓ Already complete: {lesson.title}[/dim]")
                continue

            # Navigate to lesson
            await nav.navigate_to_lesson(lesson)

            # Detect type
            lesson_type = await nav.detect_lesson_type(lesson)
            lesson.lesson_type = lesson_type

            try:
                # Handle the lesson
                course_name, _ = COURSES[course_key]
                result = await handle_lesson(
                    page, lesson, lesson_type,
                    validator=validator,
                    course_context=course_name,
                )

                # Write notes
                if lesson_type == LessonType.QUIZ and result.get("quiz_result"):
                    qr = result["quiz_result"]
                    notes.add_quiz_result(
                        lesson.title, qr.questions, qr.score_percent
                    )
                    show_quiz_result(qr)
                else:
                    notes.add_lesson(
                        lesson.title, result["type"], result.get("text", "")
                    )

                lesson.status = LessonStatus.COMPLETED
                progress.advance(task_id)

            except Exception as e:
                console.print(f"[red]  Error on '{lesson.title}': {e}[/red]")
                # Take debug screenshot
                try:
                    path = await browser.screenshot(
                        f"error_{course_key}_{lesson.title[:20]}"
                    )
                    console.print(f"[dim]  Screenshot saved: {path}[/dim]")
                except Exception:
                    pass

    # Summary
    final_completed = sum(1 for l in course.lessons if l.status == LessonStatus.COMPLETED)
    console.print(
        f"\n[bold green]{course.name}: {final_completed}/{total} lessons completed[/bold green]"
    )


async def main():
    args = parse_args()
    show_banner()

    if not args.discover:
        show_course_table(COURSES)

    browser = BrowserManager(headless=args.headless)
    notes = NotesWriter(COURSE_NOTES_PATH)
    validator: ValidatorClient | None = None

    try:
        page = await browser.launch()
        logged_in = await browser.ensure_logged_in()

        if not logged_in:
            console.print("[red]Could not verify login. Exiting.[/red]")
            return

        if args.discover:
            await run_discover(browser)
            return

        # Start MCP validator unless disabled
        if not args.no_validate and not args.dry_run:
            console.print("[cyan]Starting MCP quiz validator...[/cyan]")
            validator = ValidatorClient()
            await validator.connect()
            console.print("[green]MCP validator ready.[/green]")

        # Determine which courses to run
        course_keys = [args.course] if args.course else list(COURSES.keys())

        for key in course_keys:
            name, _ = COURSES[key]
            console.print(f"\n[bold]{'='*60}[/bold]")
            console.print(f"[bold cyan]Course: {name}[/bold cyan]")
            console.print(f"[bold]{'='*60}[/bold]\n")

            await run_course(
                browser, key, notes,
                dry_run=args.dry_run,
                validator=validator,
            )

        console.print(f"\n[bold green]All done! Notes saved to: {COURSE_NOTES_PATH}[/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        try:
            await browser.screenshot("fatal_error")
        except Exception:
            pass
        raise
    finally:
        if validator:
            await validator.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
