import json
import re
from pathlib import Path

from src.localization import catalog, language_from_header, metadata_language_from_header, translate

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
    assert language_from_header("fr_FR") == "fr"


def test_stable_errors_are_localized_but_unknown_details_are_preserved() -> None:
    assert translate("fr", "Video not found.") == "Vidéo introuvable."
    detail = "yt-dlp: remote service returned an unexpected response"
    assert translate("fr", detail) == detail
    assert catalog("en") == {}


def test_french_catalog_has_unique_keys_and_covers_the_ui() -> None:
    raw_catalog = (ROOT / "static" / "i18n" / "fr.json").read_text(encoding="utf-8")
    translations = json.loads(raw_catalog, object_pairs_hook=reject_duplicate_keys)
    sources = [
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "frontend" / "src").rglob("*"))
        if path.suffix in {".js", ".vue"}
    ]
    ui_keys = {key for source in sources for key in re.findall(r"\bt\('([^']+)'", source)}
    assert ui_keys, "No translation key found in the front-end sources."
    assert ui_keys <= translations.keys(), sorted(ui_keys - translations.keys())


def test_metadata_language_follows_the_first_preference() -> None:
    assert metadata_language_from_header("de-DE, fr;q=0.9") == "de"
    assert metadata_language_from_header("fr_FR") == "fr"
    assert metadata_language_from_header("en") == "en"
    assert metadata_language_from_header(None) == "en"


def test_metadata_language_keeps_the_region_only_where_youtube_needs_it() -> None:
    assert metadata_language_from_header("pt-BR") == "pt-BR"
    assert metadata_language_from_header("zh_cn") == "zh-CN"
    assert metadata_language_from_header("en-GB") == "en"


def test_metadata_language_rejects_anything_that_is_not_a_language_tag() -> None:
    assert metadata_language_from_header("*") == "en"
    assert metadata_language_from_header("fr; --exec") == "fr"
    assert metadata_language_from_header("--exec=calc") == "en"
