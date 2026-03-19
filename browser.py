"""Browser management with persistent Playwright context."""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page
from rich.console import Console

from config import PLAYWRIGHT_DATA_DIR, DEBUG_SCREENSHOTS_DIR, SKILLJAR_BASE
from css_selectors import LOGGED_IN_INDICATORS

console = Console()


class BrowserManager:
    """Manages a persistent Chromium browser context for Skilljar."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def launch(self) -> Page:
        """Launch browser with persistent profile. Returns the active page."""
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(PLAYWRIGHT_DATA_DIR),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        # Use existing page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        return self._page

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    async def ensure_logged_in(self, timeout: float = 120) -> bool:
        """Navigate to Skilljar and verify login. Prompts user if needed.

        Returns True when logged in, False if timed out.
        """
        await self.page.goto(SKILLJAR_BASE, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

        if await self._check_logged_in():
            console.print("[green]Already logged in to Skilljar.[/green]")
            return True

        console.print(
            "[yellow]Not logged in. Please log in manually in the browser window.[/yellow]"
        )
        console.print(f"[yellow]Waiting up to {int(timeout)}s for login...[/yellow]")

        elapsed = 0.0
        poll_interval = 2.0
        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            if await self._check_logged_in():
                console.print("[green]Login detected![/green]")
                return True

        console.print("[red]Login timeout. Please try again.[/red]")
        return False

    async def _check_logged_in(self) -> bool:
        """Check if any logged-in indicator is present on the page."""
        for selector in LOGGED_IN_INDICATORS:
            try:
                el = await self.page.query_selector(selector)
                if el:
                    return True
            except Exception:
                continue
        return False

    async def screenshot(self, name: str = "debug") -> Path:
        """Take a debug screenshot. Returns the file path."""
        path = DEBUG_SCREENSHOTS_DIR / f"{name}.png"
        await self.page.screenshot(path=str(path), full_page=True)
        return path

    async def close(self):
        """Shut down browser and Playwright."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        self._context = None
        self._page = None
        self._playwright = None
