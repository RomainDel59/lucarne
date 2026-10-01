"""Small runtime localization helpers for the ExApp API and UI bootstrap."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_LANGUAGES = {"en", "fr"}
SEPARATOR = re.compile(r"[-_]")


def language_from_header(header: str | None) -> str:
    """Return the best supported language from an Accept-Language header."""
    for preference in (header or "en").split(","):
        language = SEPARATOR.split(preference.split(";", 1)[0].strip(), 1)[0].lower()
        if language in SUPPORTED_LANGUAGES:
            return language
    return "en"


@lru_cache(maxsize=len(SUPPORTED_LANGUAGES))
def catalog(language: str) -> dict[str, str]:
    """Load a translation catalog once for the lifetime of the process."""
    path = APPLICATION_ROOT / "static" / "i18n" / f"{language}.json"
    if language not in SUPPORTED_LANGUAGES or not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def translate(language: str, message: str) -> str:
    """Translate a stable application message and preserve unknown details."""
    return catalog(language).get(message, message)
