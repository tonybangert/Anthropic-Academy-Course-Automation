"""Course and lesson navigation for Skilljar."""

from __future__ import annotations

from playwright.async_api import Page
from rich.console import Console

from config import course_url, COURSES
from models import Course, Lesson, LessonType, LessonStatus
from selectors import (
    CURRICULUM_LIST_CANDIDATES,
    CURRICULUM_SECTION_HEADER,
    LESSON_COMPLETION_INDICATORS,
    NEXT_LESSON_CANDIDATES,
    QUIZ_CONTAINER_CANDIDATES,
    WISTIA_CONTAINER,
    VIMEO_CONTAINER,
    YOUTUBE_CONTAINER,
    GENERIC_VIDEO,
)

console = Console()


async def _find_first(page: Page, candidates: list[str]):
    """Return the first matching element from a candidate selector list."""
    for sel in candidates:
        try:
            el = await page.query_selector(sel)
            if el:
                return el, sel
        except Exception:
            continue
    return None, None


class CourseNavigator:
    """Parses Skilljar course curriculum and navigates between lessons."""

    def __init__(self, page: Page):
        self.page = page

    async def load_course(self, course_key: str) -> Course:
        """Navigate to a course page and parse its curriculum."""
        name, _ = COURSES[course_key]
        url = course_url(course_key)

        console.print(f"[cyan]Loading course: {name}[/cyan]")
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(3000)

        lessons = await self._parse_curriculum()
        return Course(key=course_key, name=name, url=url, lessons=lessons)

    async def _parse_curriculum(self) -> list[Lesson]:
        """Extract lessons from the sidebar curriculum."""
        # Find the curriculum container
        curriculum_el, curriculum_sel = await _find_first(
            self.page, CURRICULUM_LIST_CANDIDATES
        )

        if not curriculum_el:
            console.print(
                "[yellow]Could not find curriculum sidebar. "
                "Falling back to link discovery.[/yellow]"
            )
            return await self._fallback_discover_lessons()

        console.print(f"[dim]Using curriculum selector: {curriculum_sel}[/dim]")

        # Get all lesson links within the curriculum
        links = await curriculum_el.query_selector_all("a[href]")
        lessons: list[Lesson] = []
        current_section = ""

        for link in links:
            # Check if there's a section header before this link
            parent = await link.evaluate_handle(
                "(el) => el.closest('li') || el.parentElement"
            )
            section_el = await parent.as_element().query_selector(
                CURRICULUM_SECTION_HEADER
            ) if parent else None
            if section_el:
                current_section = (await section_el.inner_text()).strip()

            href = await link.get_attribute("href") or ""
            title = (await link.inner_text()).strip()

            if not title or not href:
                continue

            # Check completion status
            status = LessonStatus.NOT_STARTED
            parent_li = await link.evaluate_handle(
                "(el) => el.closest('li')"
            )
            if parent_li:
                li_el = parent_li.as_element()
                if li_el:
                    for indicator in LESSON_COMPLETION_INDICATORS:
                        try:
                            check = await li_el.query_selector(indicator)
                            if check:
                                status = LessonStatus.COMPLETED
                                break
                        except Exception:
                            continue

            # Normalize URL
            if href.startswith("/"):
                href = f"https://anthropic.skilljar.com{href}"

            lessons.append(
                Lesson(
                    title=title,
                    url=href,
                    section=current_section,
                    status=status,
                )
            )

        console.print(f"[green]Found {len(lessons)} lessons[/green]")
        return lessons

    async def _fallback_discover_lessons(self) -> list[Lesson]:
        """Fallback: find lesson links anywhere on the page."""
        links = await self.page.query_selector_all(
            "a[href*='/page/'][href*='/lesson/'], "
            "a[href*='/courses/'][href*='/lessons/']"
        )
        lessons = []
        for link in links:
            href = await link.get_attribute("href") or ""
            title = (await link.inner_text()).strip()
            if title and href:
                if href.startswith("/"):
                    href = f"https://anthropic.skilljar.com{href}"
                lessons.append(Lesson(title=title, url=href))
        console.print(f"[green]Fallback found {len(lessons)} lessons[/green]")
        return lessons

    async def navigate_to_lesson(self, lesson: Lesson):
        """Go to a specific lesson by URL."""
        console.print(f"[cyan]  → {lesson.title}[/cyan]")
        await self.page.goto(lesson.url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

    async def detect_lesson_type(self, lesson: Lesson) -> LessonType:
        """Detect what type of content the current page has."""
        # Check for quiz
        for sel in QUIZ_CONTAINER_CANDIDATES:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return LessonType.QUIZ
            except Exception:
                continue

        # Check page text for quiz indicators
        body_text = await self.page.inner_text("body")
        quiz_keywords = ["Start Quiz", "Begin Quiz", "Take Quiz", "Start Assessment"]
        for kw in quiz_keywords:
            if kw in body_text:
                return LessonType.QUIZ

        # Check for video
        for sel in [WISTIA_CONTAINER, VIMEO_CONTAINER, YOUTUBE_CONTAINER, GENERIC_VIDEO]:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return LessonType.VIDEO
            except Exception:
                continue

        # Check for PDF
        pdf_el = await self.page.query_selector(
            "iframe[src*='.pdf'], embed[src*='.pdf'], a[href$='.pdf']"
        )
        if pdf_el:
            return LessonType.PDF

        # Default to text/modular content
        return LessonType.TEXT

    async def click_next_lesson(self) -> bool:
        """Click the Next Lesson button. Returns True if found and clicked."""
        for sel in NEXT_LESSON_CANDIDATES:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    await self.page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        return False

    async def is_lesson_complete(self) -> bool:
        """Check if the current lesson shows a completion indicator."""
        for sel in LESSON_COMPLETION_INDICATORS:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return True
            except Exception:
                continue
        return False
