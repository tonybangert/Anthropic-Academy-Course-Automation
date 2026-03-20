"""Course and lesson navigation for Skilljar."""

from __future__ import annotations

from playwright.async_api import Page
from rich.console import Console

from config import course_url, COURSES, SKILLJAR_BASE
from models import Course, Lesson, LessonType, LessonStatus
from css_selectors import (
    LOGGED_IN_INDICATORS,
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

        # Auto-register if not enrolled
        await self._ensure_registered()

        lessons = await self._parse_curriculum()
        return Course(key=course_key, name=name, url=url, lessons=lessons)

    async def _ensure_registered(self):
        """Click the Register/Enroll button if the course requires it."""
        register_selectors = [
            "a.purchase-button:has-text('Register')",
            "a:has-text('Register | FREE')",
            "a:has-text('Enroll')",
            "button:has-text('Register')",
            "button:has-text('Enroll')",
            ".purchase-button",
        ]
        for sel in register_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    console.print(f"[yellow]Course not enrolled -- clicking Register...[/yellow]")
                    await el.click()
                    await self.page.wait_for_timeout(5000)
                    # Registration might redirect to checkout or straight to course
                    # If we land on a checkout page, look for a confirm button
                    confirm_selectors = [
                        "button:has-text('Enroll')",
                        "button:has-text('Complete')",
                        "button:has-text('Confirm')",
                        "input[type='submit']",
                        "button[type='submit']",
                    ]
                    for csol in confirm_selectors:
                        try:
                            cbtn = await self.page.query_selector(csol)
                            if cbtn and await cbtn.is_visible():
                                await cbtn.click()
                                await self.page.wait_for_timeout(5000)
                                break
                        except Exception:
                            continue
                    console.print("[green]Registration complete.[/green]")
                    return
            except Exception:
                continue

    async def _parse_curriculum(self) -> list[Lesson]:
        """Extract lessons from the sidebar curriculum.

        Skilljar has two different DOM layouts:
        1. Pre-registration: ul.dp-curriculum with <li data-url="...">
        2. Post-registration: #curriculum-list with <a href="...">
        """
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

        # Strategy 1: Post-registration <a> links in #curriculum-list
        links = await curriculum_el.query_selector_all("a[href][role='listitem']")
        if not links:
            # Also try plain <a> with lesson hrefs
            links = await curriculum_el.query_selector_all("a[href*='/']")
            # Filter to lesson links only (have numeric path segments)
            filtered = []
            for link in links:
                href = await link.get_attribute("href") or ""
                if href and any(c.isdigit() for c in href.split("/")[-1]):
                    filtered.append(link)
            links = filtered

        if links:
            return await self._parse_link_curriculum(links)

        # Strategy 2: Pre-registration <li data-url> items
        items = await curriculum_el.query_selector_all("li[data-url]")
        if items:
            return await self._parse_li_curriculum(items)

        console.print("[yellow]No lessons found in curriculum container[/yellow]")
        return []

    async def _parse_link_curriculum(self, links) -> list[Lesson]:
        """Parse curriculum from <a> link elements (post-registration layout)."""
        lessons: list[Lesson] = []

        for link in links:
            href = await link.get_attribute("href") or ""
            classes = await link.get_attribute("class") or ""

            # Get title from .title element or inner text
            title_el = await link.query_selector(".title")
            title = ""
            if title_el:
                title = (await title_el.inner_text()).strip()
            if not title:
                title = (await link.inner_text()).strip()
                # Clean up multi-line text
                lines = [l.strip() for l in title.split("\n") if l.strip()]
                title = lines[0] if lines else title

            if not title or not href:
                continue

            # Build full URL
            url = href
            if url.startswith("/"):
                url = f"https://anthropic.skilljar.com{url}"

            # Detect type from CSS class
            lesson_type = self._detect_type_from_class(classes)

            # Check completion from class or icon
            status = LessonStatus.NOT_STARTED
            if "lesson-complete" in classes:
                status = LessonStatus.COMPLETED
            elif "lesson-incomplete" in classes:
                status = LessonStatus.NOT_STARTED
            else:
                check = await link.query_selector(".fa-check-circle, .fa-check")
                if check:
                    status = LessonStatus.COMPLETED

            lessons.append(
                Lesson(title=title, url=url, lesson_type=lesson_type, status=status)
            )

        console.print(f"[green]Found {len(lessons)} lessons[/green]")
        return lessons

    async def _parse_li_curriculum(self, items) -> list[Lesson]:
        """Parse curriculum from <li data-url> elements (pre-registration layout)."""
        lessons: list[Lesson] = []

        for item in items:
            data_url = await item.get_attribute("data-url") or ""
            classes = await item.get_attribute("class") or ""

            wrapper = await item.query_selector(".lesson-wrapper")
            title = ""
            if wrapper:
                title = (await wrapper.inner_text()).strip()
            if not title:
                title = (await item.inner_text()).strip()

            if not title or not data_url:
                continue

            url = data_url
            if url.startswith("/"):
                url = f"https://anthropic.skilljar.com{url}"

            lesson_type = self._detect_type_from_class(classes)

            status = LessonStatus.NOT_STARTED
            if "lesson-complete" in classes:
                status = LessonStatus.COMPLETED
            else:
                for indicator in LESSON_COMPLETION_INDICATORS:
                    try:
                        check = await item.query_selector(indicator)
                        if check:
                            status = LessonStatus.COMPLETED
                            break
                    except Exception:
                        continue

            lessons.append(
                Lesson(title=title, url=url, lesson_type=lesson_type, status=status)
            )

        console.print(f"[green]Found {len(lessons)} lessons[/green]")
        return lessons

    @staticmethod
    def _detect_type_from_class(classes: str) -> LessonType:
        """Detect lesson type from CSS classes."""
        if "lesson-quiz" in classes or "lesson-assessment" in classes:
            return LessonType.QUIZ
        elif "lesson-video" in classes:
            return LessonType.VIDEO
        elif "lesson-modular" in classes or "lesson-text" in classes:
            return LessonType.TEXT
        return LessonType.UNKNOWN

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

    async def check_session(self) -> bool:
        """Verify we're still logged in. Returns False if session expired."""
        for sel in LOGGED_IN_INDICATORS:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return True
            except Exception:
                continue
        # Also check if we got redirected to a login page
        url = self.page.url
        if "sign_in" in url or "login" in url:
            return False
        return True

    async def navigate_to_lesson(self, lesson: Lesson):
        """Go to a specific lesson by URL."""
        console.print(f"[cyan]  -> {lesson.title}[/cyan]")
        await self.page.goto(lesson.url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

        # Check if session expired during navigation
        if not await self.check_session():
            console.print("[yellow]  Session expired -- waiting for re-login...[/yellow]")
            import asyncio
            for _ in range(60):  # wait up to 2 minutes
                await asyncio.sleep(2)
                if await self.check_session():
                    console.print("[green]  Re-login detected, resuming.[/green]")
                    await self.page.goto(lesson.url, wait_until="domcontentloaded")
                    await self.page.wait_for_timeout(2000)
                    return
            raise RuntimeError("Session expired and re-login timed out")

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
