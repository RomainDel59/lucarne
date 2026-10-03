"""Catalogue-agent scheduling tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agent import Agent
from src.database import Database
from src.errors import LucarneError, VideoUnavailableError
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


def test_a_playlist_keeps_its_own_title_but_a_channel_takes_its_author_name(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    playlist = repository.create_playlist("alice", "Mix", "https://www.youtube.com/playlist?list=PLabcdefghijk")
    agent = make_agent(database, repository, tmp_path)
    data = {"title": "My playlist", "channel": "Alice Owner", "uploader": "Alice Owner", "entries": []}

    agent._update_source("alice", "playlist", int(playlist["id"]), data)
    agent._update_source("alice", "channel", int(channel["id"]), {**data, "title": "Alice - Videos"})

    assert repository.playlist("alice", int(playlist["id"]))["title"] == "My playlist"
    assert repository.channel("alice", int(channel["id"]))["title"] == "Alice Owner"


PRIVATE = {"id": "video_01", "reason": "Private video", "known": True, "temporary": False, "retry_after": None}
UNKNOWN = {"id": "video_03", "reason": "Something odd", "known": False, "temporary": False, "retry_after": None}


class FlakyYouTube:
    """Five videos of a channel: the second is private and the fourth fails for an unknown reason."""

    def discover(self, value: str, source_type: str, start: int, count: int, language: str) -> dict:
        return {
            "id": "UCchannel123",
            "channel": "Example channel",
            "entries": [{"id": f"video_{index:02d}", "timestamp": 1000 + index, "rank": start + index} for index in range(5)],
            "has_more": True,
            "next_offset": start - 1 + 5,
            "source_url": value,
            "image_url": None,
        }

    def inspect_batch(self, video_ids: list[str], language: str) -> tuple[list[dict], list[dict]]:
        failing = {"video_01": PRIVATE, "video_03": UNKNOWN}
        details = [
            {
                "id": video_id,
                "title": f"Title {video_id}",
                "channel": "Example channel",
                "channel_id": "UCchannel123",
                "upload_date": "20260928",
                "duration": 10,
            }
            for video_id in video_ids
            if video_id not in failing
        ]
        return details, [failing[video_id] for video_id in video_ids if video_id in failing]

    def inspect_video(self, value: str, language: str) -> dict:
        raise VideoUnavailableError("Privée", "Private video")


def hidden_rows(database: Database) -> list[tuple[str, int, bool]]:
    rows = database.all("SELECT youtube_id,skip_attempts,retry_at FROM videos WHERE availability='skipped' ORDER BY id")
    return [(row["youtube_id"], row["skip_attempts"], row["retry_at"] is not None) for row in rows]


def test_a_video_that_fails_neither_stops_its_batch_nor_blocks_the_history(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@example/videos")
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = FlakyYouTube()

    agent._history("alice", "channel", int(channel["id"]), 5)

    visible = repository.videos("alice", channel_id=channel["id"])
    assert sorted(item["youtube_id"] for item in visible["items"]) == ["video_00", "video_02", "video_04"]
    assert hidden_rows(database) == [("video_01", 1, False), ("video_03", 1, True)]
    assert repository.channel("alice", channel["id"])["catalog_offset"] == 5
    assert repository.channels("alice")[0]["video_count"] == 3


def test_a_playlist_keeps_the_place_of_a_video_that_cannot_be_read(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    playlist = repository.create_playlist("alice", "Mix", "https://www.youtube.com/playlist?list=PLabcdefghijk")
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = FlakyYouTube()

    agent._history("alice", "playlist", int(playlist["id"]), 5)

    links = database.all(
        "SELECT v.youtube_id, pv.position FROM playlist_videos pv JOIN videos v ON v.id=pv.video_id WHERE pv.playlist_id=? ORDER BY pv.position",
        (playlist["id"],),
    )
    assert [(row["youtube_id"], row["position"]) for row in links] == [(f"video_{index:02d}", index + 1) for index in range(5)]
    assert [item["youtube_id"] for item in repository.videos("alice", playlist_id=playlist["id"])["items"]] == [
        "video_00",
        "video_02",
        "video_04",
    ]
    assert repository.playlists("alice")[0]["video_count"] == 3


def test_the_metadata_phase_records_the_videos_it_cannot_read(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@example/videos")
    with database.write() as connection:
        connection.executemany(
            """INSERT INTO candidates(user_id,source_type,source_id,youtube_id,priority,status,source_rank,created_at)
               VALUES ('alice','channel',?,?,0,'pending',NULL,?)""",
            [(channel["id"], f"video_{index:02d}", now()) for index in range(5)],
        )
    ids = [row["id"] for row in database.all("SELECT id FROM candidates")]
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = FlakyYouTube()

    agent._process_candidates("alice", ids)

    assert len(repository.videos("alice")["items"]) == 3
    assert hidden_rows(database) == [("video_01", 1, False), ("video_03", 1, True)]
    assert {row["status"] for row in database.all("SELECT status FROM candidates")} == {"done"}


def test_a_video_added_by_hand_that_cannot_be_read_is_recorded_without_failing(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = FlakyYouTube()

    agent._inspect_single_video("alice", "https://www.youtube.com/watch?v=video_01", None)

    assert hidden_rows(database) == [("video_01", 1, False)]


def test_a_video_whose_time_has_come_is_read_again_and_shown_when_it_works(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@example/videos")
    repository.record_unreadable_video("alice", UNKNOWN, channel["id"], "Example channel")
    with database.write() as connection:
        connection.execute("UPDATE videos SET retry_at=1")
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = SimpleNamespace(
        inspect_batch=lambda ids, language: (
            [{"id": ids[0], "title": "Back", "channel": "Example channel", "upload_date": "20260928", "duration": 10}],
            [],
        )
    )

    agent._plan_retries("alice")
    agent._plan_retries("alice")
    jobs = database.all("SELECT * FROM agent_jobs WHERE type='retry_videos'")
    assert len(jobs) == 1 and repository.job("alice", jobs[0]["id"])["payload"] == {"youtube_ids": ["video_03"]}

    agent._execute("alice", "retry_videos", None, None, {"youtube_ids": ["video_03"]})

    video = repository.videos("alice", channel_id=channel["id"])["items"][0]
    assert (video["youtube_id"], video["title"], video["availability"], video["channel_id"]) == (
        "video_03",
        "Back",
        "available",
        channel["id"],
    )
    assert hidden_rows(database) == []


def test_a_video_that_still_fails_when_tried_again_is_scheduled_again(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    repository.record_unreadable_video("alice", UNKNOWN)
    agent = make_agent(database, repository, tmp_path)
    agent.youtube = FlakyYouTube()

    agent._retry_videos("alice", ["video_03"])

    assert hidden_rows(database) == [("video_03", 2, True)]


def test_a_channel_whose_first_video_cannot_be_read_is_still_subscribed(
    database: Database, repository: Repository, tmp_path: Path
) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@example/videos")
    agent = make_agent(database, repository, tmp_path)
    flaky = FlakyYouTube()
    agent.youtube = SimpleNamespace(
        discover=lambda url, kind, start, count, language: {
            **flaky.discover(url, kind, start, count, language),
            "entries": [{"id": "video_01", "timestamp": 1001, "rank": 1}],
            "next_offset": 1,
        },
        inspect_batch=flaky.inspect_batch,
    )

    agent._initialize_channel("alice", int(channel["id"]))

    initialized = repository.channel("alice", channel["id"])
    assert (initialized["external_id"], initialized["title"], initialized["sync_status"]) == (
        "UCchannel123",
        "Example channel",
        "idle",
    )
    assert repository.videos("alice", channel_id=channel["id"])["total"] == 0
    assert hidden_rows(database) == [("video_01", 1, False)]

