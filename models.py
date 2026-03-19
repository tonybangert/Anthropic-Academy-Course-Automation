"""Data models for courses, lessons, and quizzes."""

from dataclasses import dataclass, field
from enum import Enum


class LessonType(Enum):
    VIDEO = "video"
    TEXT = "text"
    QUIZ = "quiz"
    MODULAR = "modular"
    PDF = "pdf"
    UNKNOWN = "unknown"


class LessonStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Lesson:
    title: str
    url: str
    lesson_type: LessonType = LessonType.UNKNOWN
    status: LessonStatus = LessonStatus.NOT_STARTED
    section: str = ""


@dataclass
class Course:
    key: str
    name: str
    url: str
    lessons: list[Lesson] = field(default_factory=list)


@dataclass
class QuizQuestion:
    number: int
    text: str
    options: list[str] = field(default_factory=list)
    selected_answer: str = ""
    correct_answer: str = ""
    is_correct: bool | None = None


@dataclass
class QuizResult:
    score_percent: float
    passed: bool
    questions: list[QuizQuestion] = field(default_factory=list)
    attempt_number: int = 1
