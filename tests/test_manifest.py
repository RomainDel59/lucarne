"""AppAPI publication manifest tests."""

from pathlib import Path
from xml.etree import ElementTree

from src import __version__


def test_manifest_declares_every_proxied_surface() -> None:
    root = ElementTree.parse(Path(__file__).parents[1] / "appinfo" / "info.xml").getroot()  # noqa: S314
    routes = {
        route.findtext("url"): route.findtext("access_level") for route in root.findall("./external-app/routes/route")
    }

    assert routes["^/api/admin/.*"] == "ADMIN"
    assert routes["^/api/.*"] == "USER"
    assert routes["^/media/.*"] == "USER"
    assert routes["^/(js|css|img)/.*"] == "USER"


def test_manifest_and_runtime_versions_match() -> None:
    root = ElementTree.parse(Path(__file__).parents[1] / "appinfo" / "info.xml").getroot()  # noqa: S314

    assert root.findtext("id") == "lucarne"
    assert root.findtext("version") == __version__
    assert root.findtext("./external-app/docker-install/image-tag") == __version__


def test_container_includes_the_youtube_challenge_runtime() -> None:
    root = Path(__file__).parents[1]
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    youtube = (root / "src" / "youtube.py").read_text(encoding="utf-8")

    assert "yt-dlp[default]" in requirements
    assert "deno-${archive_arch}-unknown-linux-gnu.zip" in dockerfile
    assert '"--js-runtimes",\n                    "deno"' in youtube
