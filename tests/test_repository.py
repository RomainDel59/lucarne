"""Repository and isolation tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database import SCHEMA_VERSION, Database
from src.repository import Repository


def test_personal_settings_are_isolated(repository: Repository) -> None:
    repository.update_personal_settings(
        "alice",
        {"default_mode": "audio", "default_quality": "1080", "default_audio_quality": "192", "history_limit": 25},
    )

    assert repository.personal_settings("alice")["default_mode"] == "audio"
    assert repository.personal_settings("bob")["default_mode"] == "video"


def test_catalog_names_are_unique_without_changing_case(repository: Repository) -> None:
    catalogue = repository.create_catalog("alice", "  French   History ")

    assert catalogue["name"] == "French History"
    try:
        repository.create_catalog("alice", "french history")
    except Exception as error:
        assert "already exists" in str(error)
    else:
        raise AssertionError("Case-insensitive duplicate should fail")


def test_catalog_memberships_cannot_cross_users(repository: Repository) -> None:
    alice_channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    bob_channel = repository.create_channel("bob", "https://www.youtube.com/@bob/videos")
    catalogue = repository.create_catalog("alice", "History")

    repository.replace_catalog_channels("alice", catalogue["id"], [alice_channel["id"]])
    assert repository.catalog("alice", catalogue["id"])["channel_ids"] == [alice_channel["id"]]

    try:
        repository.replace_catalog_channels("alice", catalogue["id"], [bob_channel["id"]])
    except ValueError:
        pass
    else:
        raise AssertionError("Cross-user membership should fail")


def test_video_pagination_is_fixed_to_ten(repository: Repository) -> None:
    for index in range(12):
        repository.store_video(
            "alice",
            {
                "id": f"video_{index:02d}",
                "title": f"Video {index}",
                "timestamp": 1000 + index,
                "webpage_url": f"https://www.youtube.com/watch?v=video_{index:02d}",
            },
        )

    first = repository.videos("alice", page=1)
    second = repository.videos("alice", page=2)

    assert first["page_size"] == 10
    assert len(first["items"]) == 10
    assert len(second["items"]) == 2
    assert first["total"] == 12

    wide = repository.videos("alice", page=2, page_size=5)
    assert wide["page_size"] == 5
    assert len(wide["items"]) == 5


def test_pending_videos_share_the_fixed_page_size(repository: Repository) -> None:
    for index in range(12):
        repository.store_video(
            "alice",
            {
                "id": f"ready_{index:02d}",
                "title": f"Ready {index}",
                "timestamp": 1000 + index,
                "webpage_url": f"https://www.youtube.com/watch?v=ready_{index:02d}",
            },
        )
    for index in range(3):
        repository.enqueue(
            "alice",
            "inspect_video",
            "video",
            None,
            {"url": f"https://www.youtube.com/watch?v=pending_{index:02d}"},
        )

    pending = repository.pending_video_jobs("alice")
    first = repository.videos("alice", page=1, pending_count=len(pending))
    second = repository.videos("alice", page=2, pending_count=len(pending))

    assert len(pending) == 3
    assert len(first["items"]) + len(pending[:10]) == 10
    assert len(second["items"]) == 5
    assert first["total"] == 15


def test_manual_batches_are_prioritized(repository: Repository) -> None:
    automatic = repository.enqueue("alice", "discover", None, None, manual=False)
    manual = repository.enqueue("alice", "inspect_video", "video", None, manual=True)
    status = repository.agent_status("alice")

    queued_ids = [item["id"] for item in status["jobs"] if item["status"] == "queued"]
    assert queued_ids.index(manual["id"]) < queued_ids.index(automatic["id"])


def test_automatic_batches_keep_insertion_order(repository: Repository) -> None:
    first = repository.enqueue("alice", "discover", None, None, manual=False)
    second = repository.enqueue("alice", "metadata", None, None, manual=False)
    status = repository.agent_status("alice")

    queued_ids = [item["id"] for item in status["jobs"] if item["status"] == "queued"]
    assert queued_ids.index(first["id"]) < queued_ids.index(second["id"])


def test_pending_sources_are_not_treated_as_initialized(repository: Repository) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    playlist = repository.create_playlist(
        "alice", "Pending playlist", "https://www.youtube.com/playlist?list=PLabcdefghijk123"
    )

    assert channel["external_id"].startswith("pending_")
    assert channel["title"] == "@alice"
    assert channel["sync_status"] == "initializing"
    assert playlist["external_id"].startswith("pending_")
    assert playlist["sync_status"] == "initializing"


def test_equivalent_active_batch_is_not_duplicated(repository: Repository) -> None:
    first = repository.enqueue(
        "alice", "inspect_video", "video", None, {"url": "https://www.youtube.com/watch?v=abcdefghijk"}
    )
    second = repository.enqueue(
        "alice", "inspect_video", "video", None, {"url": "https://www.youtube.com/watch?v=abcdefghijk"}
    )

    assert first["id"] == second["id"]


def test_unsubscribing_keeps_videos_but_removes_catalog_membership(repository: Repository) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    video = repository.store_video(
        "alice",
        {
            "id": "abcdefghijk",
            "title": "Known video",
            "channel": "Alice",
            "timestamp": 1000,
            "webpage_url": "https://www.youtube.com/watch?v=abcdefghijk",
        },
        channel["id"],
    )
    catalogue = repository.create_catalog("alice", "History")
    repository.replace_catalog_channels("alice", catalogue["id"], [channel["id"]])

    repository.mark_channel_deleting("alice", channel["id"])
    repository.unsubscribe_channel("alice", channel["id"])

    assert repository.channel("alice", channel["id"])["subscribed"] == 0
    assert repository.video("alice", video["id"])["channel_id"] == channel["id"]
    assert repository.catalog("alice", catalogue["id"])["channel_ids"] == []


def test_external_video_creates_an_unsubscribed_channel(repository: Repository) -> None:
    video = repository.store_video(
        "alice",
        {
            "id": "abcdefghijk",
            "title": "Standalone video",
            "channel": "History channel",
            "channel_id": "UCabcdefghijk",
            "timestamp": 1000,
            "webpage_url": "https://www.youtube.com/watch?v=abcdefghijk",
        },
    )

    channel = repository.channel("alice", video["channel_id"])
    assert channel["subscribed"] == 0
    assert repository.channels("alice") == []


def test_history_is_paginated_by_ten(repository: Repository) -> None:
    for index in range(12):
        video = repository.store_video(
            "alice",
            {
                "id": f"history_{index:02d}",
                "title": f"History {index}",
                "timestamp": 1000 + index,
                "webpage_url": f"https://www.youtube.com/watch?v=history_{index:02d}",
            },
        )
        repository.save_history("alice", video["id"], 30, 120)

    first = repository.history("alice", 1)
    second = repository.history("alice", 2)

    assert first["page_size"] == 10
    assert first["total"] == 12
    assert len(first["items"]) == 10
    assert len(second["items"]) == 2


def test_instance_settings_accept_only_supported_schedules(repository: Repository) -> None:
    result = repository.update_instance_settings(
        {
            "batch_size": 5,
            "lot_wait_seconds": 300,
            "campaign_duration_seconds": 7200,
            "temporary_retention_days": 7,
        }
    )
    assert result["lot_wait_seconds"] == 300

    with pytest.raises(ValueError, match="delay between batches"):
        repository.update_instance_settings(
            {
                "batch_size": 10,
                "lot_wait_seconds": 301,
                "campaign_duration_seconds": 7200,
                "temporary_retention_days": 7,
            }
        )


def test_batch_size_accepts_one_video_and_rejects_the_extremes(repository: Repository) -> None:
    values = {"lot_wait_seconds": 300, "campaign_duration_seconds": 7200, "temporary_retention_days": 7}
    assert repository.update_instance_settings({**values, "batch_size": 1})["batch_size"] == 1

    for invalid in (0, 51):
        with pytest.raises(ValueError, match="batch size"):
            repository.update_instance_settings({**values, "batch_size": invalid})


def test_upload_date_is_used_when_youtube_has_no_timestamp(repository: Repository) -> None:
    video = repository.store_video(
        "alice",
        {
            "id": "dated_video",
            "title": "Dated video",
            "upload_date": "20260928",
            "webpage_url": "https://www.youtube.com/watch?v=dated_video",
        },
    )

    expected = int(datetime(2026, 9, 28, 12, tzinfo=UTC).timestamp())
    assert video["published_at"] == expected
    assert video["availability_checked_at"] is not None


def test_user_language_defaults_to_english_and_is_remembered(repository: Repository) -> None:
    assert repository.user_language("alice") == "en"

    repository.remember_language("alice", "fr")
    repository.remember_language("bob", "pt-BR")

    assert repository.user_language("alice") == "fr"
    assert repository.user_language("bob") == "pt-BR"
    assert repository.personal_settings("alice")["language"] == "fr"


def test_a_database_without_the_language_column_is_upgraded(tmp_path: Path) -> None:
    database = Database(tmp_path / "old.db")
    database.initialize()
    with database.write() as connection:
        connection.execute("INSERT INTO user_settings(user_id, created_at, updated_at) VALUES ('alice', 1, 1)")
        connection.execute("ALTER TABLE user_settings DROP COLUMN language")
        connection.execute("UPDATE schema_meta SET version=2")

    database.initialize()

    assert Repository(database).user_language("alice") == "en"
    assert (database.one("SELECT version FROM schema_meta") or {})["version"] == SCHEMA_VERSION
