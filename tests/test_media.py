"""Playback cache and retention tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.errors import ConflictError
from src.media import MediaService
from src.repository import Repository, now


def make_media(tmp_path: Path, database, repository: Repository) -> MediaService:
    config = SimpleNamespace(downloads=tmp_path / "downloads", library=tmp_path / "library", thumbnails=tmp_path)
    config.downloads.mkdir()
    config.library.mkdir()
    return MediaService(config, database, repository, SimpleNamespace())


def store_video(repository: Repository) -> dict:
    return repository.store_video(
        "alice",
        {
            "id": "abcdefghijk",
            "title": "Cached video",
            "timestamp": 1000,
            "webpage_url": "https://www.youtube.com/watch?v=abcdefghijk",
        },
    )


def insert_cached_download(database, path: Path, video_id: int, quality: str = "720") -> str:
    download_id = f"cached{quality}"
    file_name = f"{download_id}.mp4"
    (path / file_name).write_bytes(b"media")
    timestamp = now()
    with database.write() as connection:
        connection.execute(
            """INSERT INTO downloads(
                 id,user_id,video_id,mode,quality,audio_quality,status,file_name,mime_type,size,
                 retained,created_at,accessed_at,updated_at
               ) VALUES (?,?,?,'video',?,'128','ready',?,'video/mp4',5,0,?,?,?)""",
            (download_id, "alice", video_id, quality, file_name, timestamp, timestamp, timestamp),
        )
    return download_id


def test_matching_temporary_media_is_reused_when_youtube_is_unavailable(
    tmp_path: Path, database, repository: Repository
) -> None:
    video = store_video(repository)
    media = make_media(tmp_path, database, repository)
    download_id = insert_cached_download(database, media.config.downloads, video["id"])
    with database.write() as connection:
        connection.execute("UPDATE videos SET availability='unavailable' WHERE id=?", (video["id"],))

    result = media.create_download("alice", video["id"])

    assert result["id"] == download_id


def test_unavailable_video_cannot_download_a_missing_quality(tmp_path: Path, database, repository: Repository) -> None:
    video = store_video(repository)
    media = make_media(tmp_path, database, repository)
    insert_cached_download(database, media.config.downloads, video["id"], "360")
    repository.update_video_settings("alice", video["id"], {"mode": "video", "quality": "1080", "audio_quality": None})
    with database.write() as connection:
        connection.execute("UPDATE videos SET availability='unavailable' WHERE id=?", (video["id"],))

    with pytest.raises(ConflictError):
        media.create_download("alice", video["id"])


def test_retention_can_be_requested_before_the_first_download(tmp_path: Path, database, repository: Repository) -> None:
    video = store_video(repository)
    media = make_media(tmp_path, database, repository)

    result = media.retain("alice", video["id"], True)

    assert result["retained"] == 1
    assert database.one("SELECT id FROM downloads WHERE retained=1") is None


def test_retention_promotes_the_completed_requested_variant(tmp_path: Path, database, repository: Repository) -> None:
    video = store_video(repository)
    media = make_media(tmp_path, database, repository)
    old_download = insert_cached_download(database, media.config.downloads, video["id"], "360")
    selected_download = insert_cached_download(database, media.config.downloads, video["id"], "1080")

    media.retain("alice", video["id"], True)
    assert database.one("SELECT id FROM downloads WHERE retained=1") is None

    media.retain("alice", video["id"], True, selected_download)

    retained = database.one("SELECT * FROM downloads WHERE retained=1")
    assert retained is not None
    assert retained["quality"] == "1080"
    assert retained["id"] not in {old_download, selected_download}
    assert media.path_for(retained).is_file()


def test_reusing_the_selected_cached_variant_promotes_retention_intent(
    tmp_path: Path, database, repository: Repository
) -> None:
    video = store_video(repository)
    media = make_media(tmp_path, database, repository)
    selected_download = insert_cached_download(database, media.config.downloads, video["id"], "720")
    media.retain("alice", video["id"], True)

    result = media.create_download("alice", video["id"])

    assert result["status"] == "ready"
    assert result["retained"] == 1
    assert result["id"] != selected_download
    assert media.path_for(result).is_file()


def test_interrupted_downloads_are_failed_on_restart(tmp_path: Path, database, repository: Repository) -> None:
    video = store_video(repository)
    media = make_media(tmp_path, database, repository)
    timestamp = now()
    with database.write() as connection:
        connection.execute(
            """INSERT INTO downloads(id,user_id,video_id,mode,quality,audio_quality,status,created_at,accessed_at,updated_at)
               VALUES ('interrupted','alice',?,'video','720','128','downloading',?,?,?)""",
            (video["id"], timestamp, timestamp, timestamp),
        )

    assert media.recover_interrupted() == 1
    assert media.download("alice", "interrupted")["status"] == "error"
