"""Catalogue-agent scheduling tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agent import Agent
from src.database import Database
from src.errors import LucarneError
from src.repository import Repository, now


def make_agent(database: Database, repository: Repository, tmp_path: Path) -> Agent:
    config = SimpleNamespace(
        thumbnails=tmp_path / "thumbnails",
        channel_images=tmp_path / "channel-images",
        playlist_images=tmp_path / "playlist-images",
    )
    for directory in (config.thumbnails, config.channel_images, config.playlist_images):
        directory.mkdir()
    return Agent(config, database, repository, SimpleNamespace(), SimpleNamespace())


def test_pending_sources_are_excluded_from_automatic_batches(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    campaign = repository.ensure_campaign("alice")
    agent = make_agent(database, repository, tmp_path)

    agent._prepare_automatic_jobs("alice", campaign)

    jobs = database.all("SELECT * FROM agent_jobs WHERE user_id='alice'")
    assert jobs == []


def test_campaign_stays_open_while_a_manual_job_is_queued(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    job = repository.enqueue("alice", "initialize_channel", "channel", int(channel["id"]), manual=True)
    campaign = repository.ensure_campaign("alice")
    agent = make_agent(database, repository, tmp_path)

    for _ in range(3):
        agent._prepare_automatic_jobs("alice", repository.ensure_campaign("alice"))

    campaigns = database.all("SELECT * FROM campaigns WHERE user_id='alice'")
    assert [(item["id"], item["status"]) for item in campaigns] == [(campaign["id"], "running")]
    assert repository.ensure_campaign("alice")["next_lot_at"] == campaign["next_lot_at"]
    assert repository.job("alice", job["id"])["campaign_id"] == campaign["id"]


def test_campaign_finishes_when_nothing_is_left_to_do(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    campaign = repository.ensure_campaign("alice")
    agent = make_agent(database, repository, tmp_path)

    agent._prepare_automatic_jobs("alice", campaign)

    finished = database.one("SELECT * FROM campaigns WHERE id=?", (campaign["id"],)) or {}
    assert finished["status"] == "done"


def test_metadata_candidates_are_planned_in_configured_batches(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    repository.update_instance_settings(
        {
            "batch_size": 5,
            "lot_wait_seconds": 300,
            "campaign_duration_seconds": 7200,
            "temporary_retention_days": 7,
        }
    )
    campaign = repository.ensure_campaign("alice")
    with database.write() as connection:
        connection.execute("UPDATE campaigns SET phase='metadata' WHERE id=?", (campaign["id"],))
        connection.executemany(
            """INSERT INTO candidates(user_id,source_type,source_id,youtube_id,priority,status,created_at)
               VALUES ('alice','channel',1,?,?,'pending',?)""",
            [(f"video_{index:02d}", 1000 + index, now()) for index in range(12)],
        )
    campaign = database.one("SELECT * FROM campaigns WHERE id=?", (campaign["id"],)) or {}
    agent = make_agent(database, repository, tmp_path)

    agent._prepare_automatic_jobs("alice", campaign)

    jobs = database.all(
        "SELECT * FROM agent_jobs WHERE campaign_id=? AND type='metadata' ORDER BY created_at,id", (campaign["id"],)
    )
    assert [len(repository.job("alice", job["id"])["payload"]["candidate_ids"]) for job in jobs] == [5, 5, 2]


class InitializationYouTube:
    def discover(self, value: str, source_type: str, start: int, count: int, language: str) -> dict:
        assert start == 1
        assert count == 1
        return {
            "id": "UCchannel123",
            "title": "Channel videos",
            "channel": "Example channel",
            "entries": [{"id": "video12345", "timestamp": 1234}],
            "has_more": True,
            "next_offset": 1,
            "source_url": value,
            "image_url": None,
        }

    def inspect_batch(self, video_ids: list[str], language: str) -> tuple[list[dict], list[str]]:
        assert video_ids == ["video12345"]
        return (
            [
                {
                    "id": "video12345",
                    "title": "First video",
                    "channel": "Example channel",
                    "channel_id": "UCchannel123",
                    "upload_date": "20260928",
                    "duration": 120,
                }
            ],
            [],
        )


def test_channel_initialization_collects_exactly_one_video(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@example/videos")
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = InitializationYouTube()

    agent._initialize_channel("alice", channel["id"])

    initialized = repository.channel("alice", channel["id"])
    videos = repository.videos("alice", channel_id=channel["id"])
    assert initialized["external_id"] == "UCchannel123"
    assert initialized["title"] == "Example channel"
    assert initialized["catalog_offset"] == 1
    assert initialized["source_exhausted"] == 0
    assert videos["total"] == 1
    assert videos["items"][0]["title"] == "First video"


def test_thumbnail_falls_back_to_youtube_standard_image(
    database: Database, repository: Repository, tmp_path: Path, monkeypatch
) -> None:
    agent = make_agent(database, repository, tmp_path)
    attempts: list[str] = []

    def fake_download(url: str, directory: Path, identifier: str) -> str:
        attempts.append(url)
        if len(attempts) == 1:
            raise OSError("advertised image does not exist")
        return f"{identifier}-fallback.jpg"

    monkeypatch.setattr("src.agent.download_image", fake_download)
    video = agent._store_metadata(
        "alice",
        {
            "id": "abc123DEF45",
            "title": "Fallback thumbnail",
            "webpage_url": "https://www.youtube.com/watch?v=abc123DEF45",
            "thumbnails": [
                {
                    "url": "https://i.ytimg.com/vi/abc123DEF45/maxresdefault.jpg",
                    "width": 1280,
                    "height": 720,
                }
            ],
        },
    )

    assert attempts == [
        "https://i.ytimg.com/vi/abc123DEF45/maxresdefault.jpg",
        "https://i.ytimg.com/vi/abc123DEF45/hqdefault.jpg",
    ]
    assert video["thumbnail_file"].endswith("-fallback.jpg")


def test_youtube_is_queried_in_the_language_chosen_by_the_administrator(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    languages: list[str] = []

    def discover(url: str, source_type: str, start: int, count: int, language: str) -> dict:
        languages.append(language)
        return {"entries": []}

    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = SimpleNamespace(discover=discover)

    with pytest.raises(LucarneError):
        agent._initialize_channel("alice", int(channel["id"]))
    repository.update_instance_settings({"metadata_language": "fr"})
    with pytest.raises(LucarneError):
        agent._initialize_channel("alice", int(channel["id"]))

    assert languages == ["en", "fr"]
