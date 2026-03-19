"""Configuration: environment variables, course definitions, constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
PLAYWRIGHT_DATA_DIR = BASE_DIR / "playwright_data"
DEBUG_SCREENSHOTS_DIR = BASE_DIR / "debug_screenshots"
COURSE_NOTES_PATH = BASE_DIR / "course_notes.md"

# Ensure dirs exist
PLAYWRIGHT_DATA_DIR.mkdir(exist_ok=True)
DEBUG_SCREENSHOTS_DIR.mkdir(exist_ok=True)

# API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Targets
TARGET_SCORE = 98  # percent
MAX_QUIZ_RETRIES = 3

# Skilljar base
SKILLJAR_BASE = "https://anthropic.skilljar.com"

# Course map: key -> (display name, URL slug)
COURSES = {
    "agent-skills": (
        "Introduction to Agent Skills",
        "introduction-to-agent-skills",
    ),
    "claude-api": (
        "Building with the Claude API",
        "claude-with-the-anthropic-api",
    ),
    "mcp": (
        "Introduction to Model Context Protocol",
        "introduction-to-model-context-protocol",
    ),
    "claude-code": (
        "Claude Code in Action",
        "claude-code-in-action",
    ),
}


def course_url(key: str) -> str:
    """Return full Skilljar URL for a course key."""
    _, slug = COURSES[key]
    return f"{SKILLJAR_BASE}/{slug}"
