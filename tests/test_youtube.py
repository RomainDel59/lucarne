"""YouTube input boundary tests."""

import subprocess
from types import SimpleNamespace

import pytest

from src.assets import ALLOWED_IMAGE_HOSTS
from src.errors import LucarneError, VideoUnavailableError
from src.youtube import (
    YouTubeClient,
    normalize_channel_url,
    normalize_playlist_url,
    normalize_video_url,
    quality_format,
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


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: [youtube] ko_T10wLv-E: Première dans 110 minutes",
        "ERROR: [youtube] ko_T10wLv-E: Premieres in 2 hours",
        "ERROR: [youtube] ko_T10wLv-E: This live event will begin in 3 hours.",
        "ERROR: [youtube] ko_T10wLv-E: Private video. Sign in if you've been granted access to this video",
    ],
)
def test_a_video_that_cannot_be_read_yet_is_skipped_like_a_private_one(
    monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *_, **__: SimpleNamespace(returncode=1, stdout="", stderr=message)
    )

    with pytest.raises(VideoUnavailableError):
        YouTubeClient().run(["--dump-single-json", "https://www.youtube.com/watch?v=ko_T10wLv-E"])


def test_a_real_failure_is_still_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *_, **__: SimpleNamespace(returncode=1, stdout="", stderr="HTTP Error 429")
    )

    with pytest.raises(LucarneError) as caught:
        YouTubeClient().run(["--dump-single-json", "https://www.youtube.com/watch?v=ko_T10wLv-E"])
    assert not isinstance(caught.value, VideoUnavailableError)
