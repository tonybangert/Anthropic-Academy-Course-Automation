"""Handler for text, modular, and PDF lesson types.

Skilljar auto-marks these lessons as complete when the user scrolls to
the bottom, so we just need to load and scroll.
"""

from __future__ import annotations

from playwright.async_api import Page
from rich.console import Console

from css_selectors import LESSON_MAIN_CONTENT

console = Console()


async def extract_lesson_text(page: Page) -> str:
    """Extract the main text content from the current lesson page."""
    for sel in LESSON_MAIN_CONTENT.split(", "):
        try:
            el = await page.query_selector(sel.strip())
            if el:
                text = await el.inner_text()
                if text and len(text.strip()) > 50:
                    return text.strip()
        except Exception:
            continue
    # Fallback: grab body text
    try:
        return (await page.inner_text("body")).strip()
    except Exception:
        return ""


async def handle_content_lesson(page: Page) -> str:
    """Handle a text/modular/PDF lesson. Returns extracted text for notes."""
    console.print("[dim]    Handling text/content lesson...[/dim]")

    # Wait for content to load
    await page.wait_for_timeout(2000)

    # Extract text before scrolling (for notes)
    text = await extract_lesson_text(page)

    # Scroll to bottom to trigger completion
    await page.evaluate("""
        () => {
            return new Promise((resolve) => {
                const distance = 300;
                const interval = setInterval(() => {
                    window.scrollBy(0, distance);
                    if (window.scrollY + window.innerHeight >= document.body.scrollHeight - 50) {
                        clearInterval(interval);
                        resolve();
                    }
                }, 200);
                // Safety timeout
                setTimeout(() => { clearInterval(interval); resolve(); }, 15000);
            });
        }
    """)

    await page.wait_for_timeout(2000)
    console.print("[green]    [OK] Content lesson processed[/green]")
    return text
