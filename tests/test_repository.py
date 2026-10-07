"""Repository and isolation tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database import SCHEMA_VERSION, Database
from src.errors import ConflictError, NotFoundError
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


def test_adding_a_channel_keeps_its_other_catalogs(repository: Repository) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    other = repository.create_channel("alice", "https://www.youtube.com/@other/videos")
    history = repository.create_catalog("alice", "History")
    music = repository.create_catalog("alice", "Music")
    repository.replace_catalog_channels("alice", history["id"], [channel["id"], other["id"]])

    assert repository.add_channel_to_catalog("alice", music["id"], channel["id"])["added"] is True
    assert repository.add_channel_to_catalog("alice", music["id"], channel["id"])["added"] is False

    assert repository.catalog("alice", music["id"])["channel_ids"] == [channel["id"]]
    assert repository.catalog("alice", history["id"])["channel_ids"] == [channel["id"], other["id"]]

    bob_channel = repository.create_channel("bob", "https://www.youtube.com/@bob/videos")
    with pytest.raises(NotFoundError):
        repository.add_channel_to_catalog("alice", music["id"], bob_channel["id"])


def test_removing_a_channel_keeps_its_other_catalogs(repository: Repository) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    history = repository.create_catalog("alice", "History")
    music = repository.create_catalog("alice", "Music")
    repository.replace_catalog_channels("alice", history["id"], [channel["id"]])
    repository.replace_catalog_channels("alice", music["id"], [channel["id"]])

    repository.remove_channel_from_catalog("alice", music["id"], channel["id"])
    repository.remove_channel_from_catalog("alice", music["id"], channel["id"])

    assert repository.catalog("alice", music["id"])["channel_ids"] == []
    assert repository.catalog("alice", history["id"])["channel_ids"] == [channel["id"]]


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


def test_metadata_language_is_english_until_one_is_set(repository: Repository) -> None:
    assert repository.metadata_language() == "en"
    assert not repository.has_metadata_language()


def test_metadata_language_is_initialized_once_and_never_overrides_the_administrator(repository: Repository) -> None:
    repository.set_metadata_language_if_unset("fr")
    repository.set_metadata_language_if_unset("en")

    assert repository.has_metadata_language()
    assert repository.metadata_language() == "fr"


def test_the_administrator_chooses_the_metadata_language(repository: Repository) -> None:
    repository.set_metadata_language_if_unset("fr")

    assert repository.update_instance_settings({"metadata_language": "en"})["metadata_language"] == "en"
    assert repository.update_instance_settings({"batch_size": 5})["metadata_language"] == "en"
    with pytest.raises(ValueError, match="not supported"):
        repository.update_instance_settings({"metadata_language": "de"})
    with pytest.raises(ValueError, match="not supported"):
        repository.set_metadata_language_if_unset("de")


def test_a_database_without_the_metadata_language_is_upgraded(tmp_path: Path) -> None:
    database = Database(tmp_path / "old.db")
    database.initialize()
    with database.write() as connection:
        connection.execute("INSERT INTO instance_settings(singleton, updated_at) VALUES (1, 1)")
        connection.execute("ALTER TABLE instance_settings DROP COLUMN metadata_language")
        connection.execute("ALTER TABLE candidates DROP COLUMN source_rank")
        connection.execute("ALTER TABLE videos DROP COLUMN skip_attempts")
        connection.execute("ALTER TABLE videos DROP COLUMN retry_at")
        connection.execute("ALTER TABLE instance_settings DROP COLUMN show_skipped_videos")
        connection.execute("UPDATE schema_meta SET version=2")

    database.initialize()

    repository = Repository(database)
    assert not repository.has_metadata_language()
    assert repository.metadata_language() == "en"
    assert (database.one("SELECT version FROM schema_meta") or {})["version"] == SCHEMA_VERSION


def playlist_with_videos(repository: Repository, kind_url: str | None = None) -> tuple[dict, list[dict]]:
    playlist = repository.create_playlist("alice", "Mix", kind_url)
    videos = [
        repository.store_video(
            "alice",
            {"id": f"video_{index:02d}", "title": f"Video {index}", "timestamp": 1000 + index},
        )
        for index in range(4)
    ]
    return playlist, videos


def playlist_order(repository: Repository, playlist_id: int) -> list[str]:
    return [item["youtube_id"] for item in repository.videos("alice", playlist_id=playlist_id)["items"]]


def test_a_personal_playlist_keeps_the_order_of_addition_not_the_date(repository: Repository) -> None:
    playlist, videos = playlist_with_videos(repository)

    for video in (videos[2], videos[0], videos[3]):
        assert repository.attach_video("alice", playlist["id"], video["id"]) is True
    assert repository.attach_video("alice", playlist["id"], videos[0]["id"]) is False

    assert playlist_order(repository, playlist["id"]) == ["video_02", "video_00", "video_03"]


def test_moving_a_video_places_it_before_or_after_another(repository: Repository) -> None:
    playlist, videos = playlist_with_videos(repository)
    for video in videos:
        repository.attach_video("alice", playlist["id"], video["id"])

    repository.move_playlist_video("alice", playlist["id"], videos[3]["id"], videos[0]["id"], after=False)
    assert playlist_order(repository, playlist["id"]) == ["video_03", "video_00", "video_01", "video_02"]

    repository.move_playlist_video("alice", playlist["id"], videos[3]["id"], videos[1]["id"], after=True)
    assert playlist_order(repository, playlist["id"]) == ["video_00", "video_01", "video_03", "video_02"]

    with pytest.raises(NotFoundError):
        repository.move_playlist_video("alice", playlist["id"], videos[0]["id"], 9999, after=True)


def test_a_youtube_playlist_follows_the_rank_given_by_youtube(repository: Repository) -> None:
    playlist, videos = playlist_with_videos(repository, "https://www.youtube.com/playlist?list=PLabcdefghijk")
    for rank, video in zip((3, 1, 2, 4), videos, strict=True):
        repository.attach_video("alice", playlist["id"], video["id"], rank)

    assert playlist_order(repository, playlist["id"]) == ["video_01", "video_02", "video_00", "video_03"]

    repository.attach_video("alice", playlist["id"], videos[3]["id"], 1)
    assert playlist_order(repository, playlist["id"])[0] in {"video_01", "video_03"}


def unreadable(identifier: str, **values: object) -> dict:
    return {"id": identifier, "reason": "Private video", "known": True, "temporary": False, "retry_after": None, **values}


def test_a_video_that_cannot_be_read_is_kept_but_hidden_with_its_reason(repository: Repository) -> None:
    channel = repository.create_channel("alice", "https://www.youtube.com/@alice/videos")
    playlist = repository.create_playlist("alice", "Mix", "https://www.youtube.com/playlist?list=PLabcdefghijk")
    readable = repository.store_video("alice", {"id": "video_ok_1", "title": "Readable", "timestamp": 1000}, channel["id"])
    repository.attach_video("alice", playlist["id"], readable["id"], 1)

    skipped = repository.record_unreadable_video("alice", unreadable("video_bad1"), channel["id"], "Alice")
    repository.attach_video("alice", playlist["id"], skipped["id"], 2)

    assert (skipped["availability"], skipped["unavailable_reason"], skipped["retry_at"]) == ("skipped", "Private video", None)
    assert skipped["title"] == "video_bad1" and skipped["channel_name"] == "Alice"
    assert [item["youtube_id"] for item in repository.videos("alice")["items"]] == ["video_ok_1"]
    assert [item["youtube_id"] for item in repository.videos("alice", playlist_id=playlist["id"])["items"]] == [
        "video_ok_1"
    ]
    assert repository.channel("alice", channel["id"]) and repository.channels("alice")[0]["video_count"] == 1
    assert repository.playlists("alice")[0]["video_count"] == 1
    assert repository.video("alice", skipped["id"])["youtube_id"] == "video_bad1"


def test_a_failure_with_an_unknown_cause_says_nothing_about_a_readable_video(repository: Repository) -> None:
    video = repository.store_video("alice", {"id": "video_ok_1", "title": "Readable", "timestamp": 1000})

    assert repository.record_unreadable_video("alice", unreadable("video_ok_1", known=False)) is None
    assert repository.video("alice", video["id"])["availability"] == "available"

    repository.record_unreadable_video("alice", unreadable("video_ok_1", reason="Video unavailable"))
    changed = repository.video("alice", video["id"])
    assert (changed["availability"], changed["unavailable_reason"]) == ("unavailable", "Video unavailable")
    assert [item["youtube_id"] for item in repository.videos("alice")["items"]] == ["video_ok_1"]


def test_a_video_that_cannot_be_read_is_tried_again_until_it_is_given_up(repository: Repository) -> None:
    unknown = unreadable("video_bad1", known=False, reason="Something odd")

    first = repository.record_unreadable_video("alice", unknown)
    assert (first["skip_attempts"], first["retry_at"] is not None) == (1, True)
    assert repository.due_retries("alice", 10) == []

    with repository.db.write() as connection:
        connection.execute("UPDATE videos SET retry_at=1 WHERE id=?", (first["id"],))
    assert [item["youtube_id"] for item in repository.due_retries("alice", 10)] == ["video_bad1"]

    second = repository.record_unreadable_video("alice", unknown)
    assert second["id"] == first["id"] and second["skip_attempts"] == 2 and second["retry_at"] is not None
    third = repository.record_unreadable_video("alice", unknown)
    assert (third["skip_attempts"], third["retry_at"]) == (3, None)
    assert repository.due_retries("alice", 10) == []


def test_a_video_that_is_read_again_becomes_whole_again(repository: Repository) -> None:
    skipped = repository.record_unreadable_video("alice", unreadable("video_bad1", known=False, reason="Something odd"))

    video = repository.store_video("alice", {"id": "video_bad1", "title": "Back", "timestamp": 1000})

    assert video["id"] == skipped["id"]
    assert (video["availability"], video["unavailable_reason"], video["skip_attempts"], video["retry_at"]) == (
        "available",
        None,
        0,
        None,
    )
    assert [item["youtube_id"] for item in repository.videos("alice")["items"]] == ["video_bad1"]


def test_a_video_waiting_to_be_deleted_is_not_recorded_again(repository: Repository) -> None:
    video = repository.store_video("alice", {"id": "video_ok_1", "title": "Readable", "timestamp": 1000})
    repository.mark_video_deleting("alice", video["id"])

    assert repository.record_unreadable_video("alice", unreadable("video_ok_1")) is None


def test_videos_are_placed_by_their_publication_date_or_else_by_the_date_they_were_added(
    repository: Repository,
) -> None:
    repository.store_video("alice", {"id": "video_old1", "title": "Old", "timestamp": 1000})
    repository.store_video("alice", {"id": "video_nodate", "title": "No date"})

    assert [item["youtube_id"] for item in repository.videos("alice")["items"]] == ["video_nodate", "video_old1"]


def test_the_videos_that_could_not_be_read_stay_hidden_until_an_administrator_shows_them(
    repository: Repository,
) -> None:
    repository.store_video("alice", {"id": "video_ok_1", "title": "Readable", "timestamp": 1000})
    repository.record_unreadable_video("alice", unreadable("video_bad1"))

    assert repository.show_skipped_videos() is False
    assert [item["youtube_id"] for item in repository.videos("alice")["items"]] == ["video_ok_1"]

    repository.update_instance_settings({"show_skipped_videos": True})
    shown = repository.videos("alice")
    assert repository.show_skipped_videos() is True
    assert shown["total"] == 2
    assert {item["youtube_id"]: item["availability"] for item in shown["items"]} == {
        "video_ok_1": "available",
        "video_bad1": "skipped",
    }

    repository.update_instance_settings({"batch_size": 20})
    assert repository.show_skipped_videos() is True
    repository.update_instance_settings({"show_skipped_videos": False})
    assert repository.videos("alice")["total"] == 1


def test_a_video_that_could_not_be_read_is_tried_again_on_request(repository: Repository) -> None:
    video = repository.record_unreadable_video("alice", unreadable("video_bad1", known=False, reason="Something odd"))
    readable = repository.store_video("alice", {"id": "video_ok_1", "title": "Readable", "timestamp": 1000})

    job = repository.request_video_retry("alice", video["id"])

    assert job["type"] == "retry_videos" and job["payload"] == {"youtube_ids": ["video_bad1"]}
    waiting = repository.video("alice", video["id"])
    assert (waiting["skip_attempts"], waiting["retry_at"]) == (0, None)
    assert repository.request_video_retry("alice", video["id"])["id"] == job["id"]
    with pytest.raises(ConflictError):
        repository.request_video_retry("alice", readable["id"])

