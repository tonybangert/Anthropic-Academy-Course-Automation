"""Handler for video lessons (Wistia, Vimeo, YouTube).

Primary strategy: use Wistia JS API to skip to end.
Fallback: wait for the lesson to auto-complete.
"""

from __future__ import annotations

from playwright.async_api import Page
from rich.console import Console

from selectors import WISTIA_CONTAINER, VIMEO_CONTAINER, YOUTUBE_CONTAINER

console = Console()


async def _try_wistia_skip(page: Page) -> bool:
    """Attempt to skip a Wistia video to near the end using its JS API."""
    try:
        result = await page.evaluate("""
            () => {
                // Wistia exposes window._wq or Wistia.api()
                if (typeof Wistia !== 'undefined') {
                    const videos = Wistia.api.all();
                    if (videos && videos.length > 0) {
                        const player = videos[0];
                        const duration = player.duration();
                        player.time(duration - 1);
                        player.play();
                        return { success: true, duration: duration };
                    }
                }
                // Alternative: try _wq
                if (window._wq && window._wq.length > 0) {
                    return { success: false, reason: '_wq exists but needs init' };
                }
                return { success: false, reason: 'Wistia not found' };
            }
        """)
        if result and result.get("success"):
            console.print(
                f"[green]    ✓ Wistia skip: jumped to {result['duration']:.0f}s[/green]"
            )
            return True
    except Exception as e:
        console.print(f"[dim]    Wistia API attempt: {e}[/dim]")
    return False


async def _try_wistia_via_wq(page: Page) -> bool:
    """Try the _wq queue approach for Wistia."""
    try:
        result = await page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    window._wq = window._wq || [];
                    window._wq.push({
                        id: '_all',
                        onReady: function(player) {
                            const duration = player.duration();
                            player.time(duration - 1);
                            player.play();
                            resolve({ success: true, duration: duration });
                        }
                    });
                    setTimeout(() => resolve({ success: false }), 5000);
                });
            }
        """)
        if result and result.get("success"):
            console.print(
                f"[green]    ✓ Wistia _wq skip to {result['duration']:.0f}s[/green]"
            )
            return True
    except Exception:
        pass
    return False


async def _try_html5_video_skip(page: Page) -> bool:
    """Fallback: try to skip any HTML5 <video> element."""
    try:
        result = await page.evaluate("""
            () => {
                const video = document.querySelector('video');
                if (video && video.duration) {
                    video.currentTime = video.duration - 1;
                    video.play();
                    return { success: true, duration: video.duration };
                }
                return { success: false };
            }
        """)
        if result and result.get("success"):
            console.print(
                f"[green]    ✓ HTML5 video skip to {result['duration']:.0f}s[/green]"
            )
            return True
    except Exception:
        pass
    return False


async def handle_video_lesson(page: Page) -> str:
    """Handle a video lesson. Returns description text for notes."""
    console.print("[dim]    Handling video lesson...[/dim]")

    # Wait for video player to initialize
    await page.wait_for_timeout(3000)

    # Extract any visible description/transcript for notes
    description = ""
    for sel in [".video-description", ".lesson-description", ".transcript", "p"]:
        try:
            els = await page.query_selector_all(sel)
            texts = []
            for el in els[:5]:
                t = (await el.inner_text()).strip()
                if t and len(t) > 20:
                    texts.append(t)
            if texts:
                description = "\n".join(texts)
                break
        except Exception:
            continue

    # Detect video type and try to skip
    wistia = await page.query_selector(WISTIA_CONTAINER)
    skipped = False

    if wistia:
        skipped = await _try_wistia_skip(page)
        if not skipped:
            skipped = await _try_wistia_via_wq(page)

    if not skipped:
        skipped = await _try_html5_video_skip(page)

    if skipped:
        # Wait for video to "finish" and Skilljar to register completion
        await page.wait_for_timeout(5000)
    else:
        console.print(
            "[yellow]    Could not skip video. Waiting for auto-completion...[/yellow]"
        )
        # Wait a reasonable time — the user may need to interact
        await page.wait_for_timeout(10000)

    console.print("[green]    ✓ Video lesson processed[/green]")
    return description
