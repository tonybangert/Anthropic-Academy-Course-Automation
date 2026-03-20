"""Centralized CSS selectors for Skilljar DOM elements.

Skilljar's quiz internals are undocumented and may vary, so we use
candidate lists and discover which selector works at runtime.
"""

# -- Auth -----------------------------------------------------------------
LOGGED_IN_INDICATORS = [
    "a[href*='logout']",
    ".signout-link",
    "[class*='profile-dropdown']",
    "[class*='account-nav']",
    "a[href*='sign_out']",
    "a[href*='accounts/profile']",
]

LOGIN_LINK = "a[href*='sign_in'], a[href*='login']"

# -- Course / Curriculum ---------------------------------------------------
CURRICULUM_LIST_CANDIDATES = [
    "ul.dp-curriculum",
    "#curriculum-list",
    ".curriculum-list",
    "[data-testid='curriculum']",
    ".sj-curriculum",
    "ul.sj-sidebar-list",
]

CURRICULUM_SECTION_HEADER = "h3, h4, .section-title, .dp-section-title"

CURRICULUM_LESSON_LINK = "a"  # within curriculum list items

LESSON_COMPLETION_INDICATORS = [
    ".sj-ribbon-complete",
    ".completed",
    ".checkmark",
    "[data-completed='true']",
    "svg.check-icon",
    ".fa-check",
    ".sj-icon-check",
]

# -- Navigation ------------------------------------------------------------
NEXT_LESSON_CANDIDATES = [
    "a[class*='next-lesson']",
    "a:has-text('Next')",
    "button:has-text('Next')",
    ".next-lesson-button",
    "a.next-lesson",
    ".sj-next-lesson",
    "a:has-text('Next Lesson')",
    "a[rel='next']",
]

PREV_LESSON_CANDIDATES = [
    ".prev-lesson-button",
    "a.prev-lesson",
    "[data-testid='prev-lesson']",
    ".sj-prev-lesson",
    "a[rel='prev']",
    "button:has-text('Previous')",
    "a:has-text('Previous Lesson')",
]

# -- Lesson Content --------------------------------------------------------
LESSON_MAIN_CONTENT = "#lesson-main-content, .lesson-content, .sj-lesson-content, main"

# -- Quiz -----------------------------------------------------------------
QUIZ_CONTAINER_CANDIDATES = [
    "#quiz-container",
    ".quiz-container",
    "[data-testid='quiz']",
    ".sj-quiz",
    "form.quiz",
    ".quiz-wrapper",
    ".assessment-container",
]

QUIZ_START_BUTTON_CANDIDATES = [
    "button:has-text('Start Quiz')",
    "button:has-text('Begin Quiz')",
    "button:has-text('Start Assessment')",
    "button:has-text('Take Quiz')",
    "button:has-text('Retake Quiz')",
    "button:has-text('Retry')",
    "a:has-text('Start Quiz')",
    "a:has-text('Retake')",
]

QUIZ_QUESTION_CANDIDATES = [
    ".quiz-question",
    ".question",
    "[data-testid='question']",
    ".sj-question",
    ".question-container",
    "fieldset",
    ".assessment-question",
]

QUIZ_QUESTION_TEXT_CANDIDATES = [
    ".question-text",
    ".question-title",
    "legend",
    "h3",
    "h4",
    "p.question",
    ".prompt",
]

QUIZ_OPTION_CANDIDATES = [
    "label",
    ".answer-option",
    ".quiz-option",
    "[data-testid='option']",
    ".sj-option",
    ".choice",
]

QUIZ_RADIO_CANDIDATES = [
    "input[type='radio']",
    "input[type='checkbox']",
]

QUIZ_SUBMIT_CANDIDATES = [
    "button:has-text('Submit')",
    "button:has-text('Submit Quiz')",
    "button:has-text('Submit Answers')",
    "button[type='submit']",
    "input[type='submit']",
    "a:has-text('Submit')",
]

QUIZ_SCORE_CANDIDATES = [
    ".quiz-score",
    ".score",
    ".result-score",
    "[data-testid='score']",
    ".sj-quiz-score",
    ".grade",
    ".assessment-score",
]

QUIZ_RESULT_CONTAINER_CANDIDATES = [
    ".quiz-results",
    ".results-container",
    ".quiz-result",
    "[data-testid='results']",
    ".assessment-results",
]

QUIZ_CORRECT_INDICATOR = [
    ".correct",
    ".is-correct",
    "[data-correct='true']",
    ".sj-correct",
]

QUIZ_INCORRECT_INDICATOR = [
    ".incorrect",
    ".is-incorrect",
    ".wrong",
    "[data-correct='false']",
    ".sj-incorrect",
]

# -- Video Players ---------------------------------------------------------
WISTIA_CONTAINER = "[class*='wistia'], .wistia_embed, .wistia_responsive_padding"
VIMEO_CONTAINER = "iframe[src*='vimeo']"
YOUTUBE_CONTAINER = "iframe[src*='youtube'], iframe[src*='youtu.be']"
GENERIC_VIDEO = "video"

# -- Completion / Progress -------------------------------------------------
LESSON_COMPLETE_BANNER = [
    ".sj-ribbon-complete",
    ".lesson-complete",
    "[data-testid='lesson-complete']",
    ".completion-message",
    ":has-text('Lesson Complete')",
]
