import json
import re
from pathlib import Path

from src.localization import catalog, language_from_header, translate

ROOT = Path(__file__).resolve().parent.parent


def reject_duplicate_keys(pairs: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in pairs:
        assert key not in result, f"Duplicate translation key: {key}"
        result[key] = value
    return result


def test_language_negotiation_uses_first_supported_language() -> None:
    assert language_from_header("de-DE, fr-FR;q=0.9, en;q=0.8") == "fr"
    assert language_from_header("en-US,en;q=0.9") == "en"
    assert language_from_header(None) == "en"


def test_stable_errors_are_localized_but_unknown_details_are_preserved() -> None:
    assert translate("fr", "Video not found.") == "Vidéo introuvable."
    detail = "yt-dlp: remote service returned an unexpected response"
    assert translate("fr", detail) == detail
    assert catalog("en") == {}


def test_french_catalog_has_unique_keys_and_covers_the_ui() -> None:
    raw_catalog = (ROOT / "static" / "i18n" / "fr.json").read_text(encoding="utf-8")
    translations = json.loads(raw_catalog, object_pairs_hook=reject_duplicate_keys)
    javascript = (ROOT / "static" / "js" / "lucarne-main.js").read_text(encoding="utf-8")
    ui_keys = set(re.findall(r"\bt\('([^']+)'", javascript))
    assert ui_keys <= translations.keys()
