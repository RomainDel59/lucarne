"""YouTube input boundary tests."""

import subprocess
from types import SimpleNamespace

import pytest

from src.assets import ALLOWED_IMAGE_HOSTS
from src.errors import LucarneError, VideoUnavailableError, YtDlpError
from src.youtube import (
    YouTubeClient,
    classify_failure,
    normalize_channel_url,
    normalize_playlist_url,
    normalize_video_url,
    quality_format,
    release_delay,
)


def test_normalize_channel_url() -> None:
    assert normalize_channel_url("https://www.youtube.com/@example") == "https://www.youtube.com/@example/videos"


def test_normalize_video_url_strips_unrelated_parameters() -> None:
    assert (
        normalize_video_url("https://www.youtube.com/watch?v=abcdefghijk&t=30")
        == "https://www.youtube.com/watch?v=abcdefghijk"
    )


def test_normalize_playlist_url() -> None:
    assert (
        normalize_playlist_url("https://youtube.com/playlist?list=PLabcdefghijk123")
        == "https://www.youtube.com/playlist?list=PLabcdefghijk123"
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://www.youtube.com/watch?v=abcdefghijk",
        "https://example.org/watch?v=abcdefghijk",
        "https://www.youtube.com/embed/abcdefghijk",
    ],
)
def test_reject_unsafe_video_urls(value: str) -> None:
    with pytest.raises(LucarneError):
        normalize_video_url(value)


def test_video_format_applies_both_video_and_audio_quality() -> None:
    value = quality_format("720", "128")

    assert "height<=720" in value
    assert "abr<=128" in value
    assert "vcodec^=avc1" in value


def test_audio_quality_of_64_kbps_is_supported() -> None:
    assert "abr<=64" in quality_format("720", "64")


def test_both_youtube_channel_image_hosts_are_allowed() -> None:
    assert {"yt3.ggpht.com", "yt3.googleusercontent.com"} <= ALLOWED_IMAGE_HOSTS


def captured_command(monkeypatch: pytest.MonkeyPatch, **options: str | None) -> list[str]:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    YouTubeClient().run(["--dump-single-json", "https://www.youtube.com/watch?v=abcdefghijk"], **options)
    return commands[0]


def test_metadata_is_requested_in_the_given_language(monkeypatch: pytest.MonkeyPatch) -> None:
    command = captured_command(monkeypatch, language="de")

    assert command[command.index("--extractor-args") + 1] == "youtube:lang=de"


def test_no_language_is_forced_when_none_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "--extractor-args" not in captured_command(monkeypatch)


@pytest.mark.parametrize("value", ["", "fr; --exec", "--exec", "FR", "fr-fr", "français"])
def test_an_unexpected_language_is_never_passed_to_yt_dlp(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    assert "--extractor-args" not in captured_command(monkeypatch, language=value)


URL = "https://www.youtube.com/watch?v=ko_T10wLv-E"


def failing_yt_dlp(monkeypatch: pytest.MonkeyPatch, messages: dict[str, str]) -> list[str | None]:
    """Make yt-dlp fail with the message of the requested language; return the languages that were requested."""
    requested: list[str | None] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        language = command[command.index("--extractor-args") + 1].split("=")[1] if "--extractor-args" in command else None
        requested.append(language)
        return SimpleNamespace(returncode=1, stdout="", stderr=messages[language or "en"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    return requested


@pytest.mark.parametrize(
    "english",
    [
        "ERROR: [youtube] ko_T10wLv-E: Premieres in 2 hours",
        "ERROR: [youtube] ko_T10wLv-E: This live event will begin in 3 hours.",
        "ERROR: [youtube] ko_T10wLv-E: Private video. Sign in if you've been granted access to this video",
        "ERROR: [youtube] ko_T10wLv-E: Sign in to confirm your age. Use --cookies-from-browser or --cookies",
    ],
)
def test_the_reason_of_a_failure_is_read_in_english_to_skip_a_video(
    monkeypatch: pytest.MonkeyPatch, english: str
) -> None:
    requested = failing_yt_dlp(monkeypatch, {"fr": "ERROR: [youtube] ko_T10wLv-E: Connexion requise", "en": english})

    with pytest.raises(VideoUnavailableError) as caught:
        YouTubeClient().run(["--dump-single-json", URL], language="fr")

    assert requested == ["fr", "en"]
    assert "Connexion requise" in str(caught.value)


@pytest.mark.parametrize("language", [None, "en"])
def test_an_english_failure_is_not_asked_twice(monkeypatch: pytest.MonkeyPatch, language: str | None) -> None:
    requested = failing_yt_dlp(monkeypatch, {"en": "ERROR: [youtube] ko_T10wLv-E: Premieres in 2 hours"})

    with pytest.raises(VideoUnavailableError):
        YouTubeClient().run(["--dump-single-json", URL], language=language)

    assert len(requested) == 1


def test_a_real_failure_is_still_an_error_whatever_the_language(monkeypatch: pytest.MonkeyPatch) -> None:
    requested = failing_yt_dlp(monkeypatch, {"fr": "ERREUR : trop de requêtes (429)", "en": "HTTP Error 429"})

    with pytest.raises(LucarneError) as caught:
        YouTubeClient().run(["--dump-single-json", URL], language="fr")

    assert not isinstance(caught.value, VideoUnavailableError)
    assert str(caught.value) == "ERREUR : trop de requêtes (429)"
    assert requested == ["fr", "en"]


def test_a_failure_that_succeeds_the_second_time_stays_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = iter([SimpleNamespace(returncode=1, stdout="", stderr="Connexion requise"), SimpleNamespace(returncode=0, stdout="{}", stderr="")])
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: next(calls))

    with pytest.raises(LucarneError) as caught:
        YouTubeClient().run(["--dump-single-json", URL], language="fr")

    assert not isinstance(caught.value, VideoUnavailableError)


@pytest.mark.parametrize(
    ("message", "seconds"),
    [
        ("ERROR: [youtube] abc: Premieres in 110 minutes", 6600),
        ("ERROR: [youtube] abc: Premieres in 2 hours", 7200),
        ("ERROR: [youtube] abc: This live event will begin in 3 days.", 3 * 86400),
        ("ERROR: [youtube] abc: Premieres in an hour", 3600),
        ("ERROR: [youtube] abc: Premieres in about 5 minutes", 300),
        ("ERROR: [youtube] abc: Premieres on a date nobody can parse", None),
        ("ERROR: [youtube] abc: Private video", None),
    ],
)
def test_the_start_of_a_premiere_is_read_in_the_message(message: str, seconds: int | None) -> None:
    assert release_delay(message) == seconds


def test_a_failure_is_described_by_its_cause() -> None:
    private = classify_failure("abc", VideoUnavailableError("Privée", "Private video"))
    premiere = classify_failure("abc", VideoUnavailableError("Première", "Premieres in 2 hours"))
    unknown = classify_failure("abc", YtDlpError("Erreur", "Something odd"))

    assert (private["known"], private["temporary"], private["retry_after"], private["reason"]) == (
        True,
        False,
        None,
        "Private video",
    )
    assert (premiere["known"], premiere["temporary"], premiere["retry_after"]) == (True, True, 7200)
    assert (unknown["known"], unknown["temporary"], unknown["reason"]) == (False, False, "Something odd")


def test_a_video_that_cannot_be_read_never_stops_the_others_of_the_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_inspect(self: YouTubeClient, value: str, language: str = "en") -> dict:
        identifier = value.rsplit("=", 1)[1]
        if identifier == "video_bad1":
            raise VideoUnavailableError("Privée", "Private video")
        if identifier == "video_bad2":
            raise YtDlpError("Erreur", "Something odd")
        return {"id": identifier}

    monkeypatch.setattr(YouTubeClient, "inspect_video", fake_inspect)
    monkeypatch.setattr("src.youtube.time.sleep", lambda _: None)

    entries, failures = YouTubeClient().inspect_batch(["video_ok_1", "video_bad1", "video_bad2", "video_ok_2"])

    assert [item["id"] for item in entries] == ["video_ok_1", "video_ok_2"]
    assert [(item["id"], item["known"]) for item in failures] == [("video_bad1", True), ("video_bad2", False)]


def scripted_yt_dlp(monkeypatch: pytest.MonkeyPatch, plain: str, flagged: SimpleNamespace | None) -> list[bool]:
    """Fail with `plain` when yt-dlp is not told to ignore missing formats, else answer with `flagged`."""
    asked: list[bool] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        ignoring = "--ignore-no-formats-error" in command
        asked.append(ignoring)
        if ignoring:
            assert flagged is not None
            return flagged
        return SimpleNamespace(returncode=1, stdout="", stderr=plain)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return asked


def upcoming(stamp: int | None, status: str = "is_upcoming") -> SimpleNamespace:
    return SimpleNamespace(
        returncode=0, stdout=f'{{"id": "abc", "live_status": "{status}", "release_timestamp": {stamp or "null"}}}', stderr=""
    )


def test_the_exact_start_of_a_premiere_is_asked_to_youtube(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = scripted_yt_dlp(monkeypatch, "ERROR: [youtube] abc: Premieres in 9 hours", upcoming(2_000_000_000))
    monkeypatch.setattr("src.youtube.time.time", lambda: 2_000_000_000 - 32_400 - 3_600 + 60)

    with pytest.raises(VideoUnavailableError) as caught:
        YouTubeClient().inspect_video(URL)

    assert asked == [False, True]
    failure = classify_failure("abc", caught.value)
    assert (failure["temporary"], failure["retry_after"]) == (True, 32_400 + 3_600 - 60)


def test_the_delay_of_the_message_is_used_when_youtube_gives_no_start(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted_yt_dlp(monkeypatch, "ERROR: [youtube] abc: Premieres in 9 hours", upcoming(None))

    with pytest.raises(VideoUnavailableError) as caught:
        YouTubeClient().inspect_video(URL)

    assert getattr(caught.value, "release_timestamp", "missing") is None
    assert classify_failure("abc", caught.value)["retry_after"] == 9 * 3600


def test_a_start_too_close_is_not_looked_at_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted_yt_dlp(monkeypatch, "ERROR: [youtube] abc: Premieres in 1 minute", upcoming(2_000_000_010))
    monkeypatch.setattr("src.youtube.time.time", lambda: 2_000_000_000)

    with pytest.raises(VideoUnavailableError) as caught:
        YouTubeClient().inspect_video(URL)

    assert classify_failure("abc", caught.value)["retry_after"] == 300


def test_the_start_is_only_asked_for_a_premiere(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = scripted_yt_dlp(monkeypatch, "ERROR: [youtube] abc: Private video", None)

    with pytest.raises(VideoUnavailableError):
        YouTubeClient().inspect_video(URL)

    assert asked == [False]


def test_a_video_that_is_not_upcoming_gives_no_start(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted_yt_dlp(monkeypatch, "ERROR: [youtube] abc: Premieres in 9 hours", upcoming(2_000_000_000, "not_live"))

    with pytest.raises(VideoUnavailableError) as caught:
        YouTubeClient().inspect_video(URL)

    assert getattr(caught.value, "release_timestamp", "missing") is None


def test_the_reason_kept_is_the_message_of_youtube_without_the_yt_dlp_prefix() -> None:
    private = classify_failure("abc", VideoUnavailableError("x", "ERROR: [youtube] abc: Private video"))
    plain = classify_failure("abc", YtDlpError("x", "Something odd"))

    assert private["reason"] == "Private video"
    assert plain["reason"] == "Something odd"

