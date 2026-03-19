"""Rich CLI progress display."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn

from models import Course, Lesson, LessonStatus, QuizResult
from config import COURSES, TARGET_SCORE

console = Console()


def show_banner():
    """Display the application banner."""
    console.print(
        Panel(
            "[bold cyan]Anthropic Academy Course Automator[/bold cyan]\n"
            f"[dim]Target score: {TARGET_SCORE}% | Courses: {len(COURSES)}[/dim]",
            border_style="cyan",
        )
    )


def show_course_table(courses: dict[str, str]):
    """Show available courses in a table."""
    table = Table(title="Target Courses", border_style="cyan")
    table.add_column("Key", style="bold")
    table.add_column("Course Name")
    table.add_column("Slug", style="dim")

    for key, (name, slug) in courses.items():
        table.add_row(key, name, slug)

    console.print(table)


def show_curriculum(course: Course):
    """Display the parsed curriculum for a course."""
    table = Table(title=f"Curriculum: {course.name}", border_style="green")
    table.add_column("#", style="dim", width=4)
    table.add_column("Lesson", min_width=30)
    table.add_column("Section", style="dim")
    table.add_column("Status", width=12)

    for i, lesson in enumerate(course.lessons, 1):
        status_style = "green" if lesson.status == LessonStatus.COMPLETED else "yellow"
        status_text = lesson.status.value.replace("_", " ").title()
        table.add_row(
            str(i),
            lesson.title,
            lesson.section or "-",
            f"[{status_style}]{status_text}[/{status_style}]",
        )

    console.print(table)


def show_quiz_result(result: QuizResult):
    """Display quiz results."""
    style = "green" if result.passed else "red"
    console.print(
        Panel(
            f"[{style}]Score: {result.score_percent:.0f}%[/{style}] "
            f"(Attempt {result.attempt_number}) "
            f"[{'green' if result.passed else 'red'}]"
            f"{'PASSED' if result.passed else 'FAILED'}"
            f"[/{'green' if result.passed else 'red'}]",
            title="Quiz Result",
            border_style=style,
        )
    )


def create_progress() -> Progress:
    """Create a Rich progress bar for lesson processing."""
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    )
