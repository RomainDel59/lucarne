"""FastAPI entry point for the Lucarne Nextcloud ExApp."""

from __future__ import annotations

import logging
import mimetypes
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from nc_py_api import AsyncNextcloudApp
from nc_py_api.ex_app import AppAPIAuthMiddleware, anc_app, run_app, set_handlers

from .agent import Agent
from .config import settings
from .database import Database
from .errors import ConflictError, LucarneError, NotFoundError
from .localization import catalog, language_from_header, translate
from .media import MediaService
from .repository import Repository
from .schemas import (
    CatalogChannelsRequest,
    CatalogRequest,
    DeleteRequest,
    HistoryRequest,
    InstanceSettingsRequest,
    MoveRequest,
    PersonalSettingsRequest,
    PlaybackUpdate,
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistVideoRequest,
    RetentionRequest,
    UrlPayload,
)
from .youtube import YouTubeClient, normalize_channel_url, normalize_playlist_url, normalize_video_url

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

database = Database(settings.database)
repository = Repository(database)
youtube = YouTubeClient()
media = MediaService(settings, database, repository, youtube)
agent = Agent(settings, database, repository, youtube, media)
APPLICATION_ROOT = Path(__file__).resolve().parent.parent


async def enabled_handler(enabled: bool, nc: AsyncNextcloudApp) -> str:
    """Register or remove all Nextcloud UI resources."""
    if enabled:
        await nc.ui.top_menu.register("main", "Lucarne", "img/app.svg")
        await nc.ui.resources.set_script("top_menu", "main", "js/lucarne-main")
        await nc.ui.resources.set_style("top_menu", "main", "css/lucarne")
    else:
        await nc.ui.resources.delete_script("top_menu", "main", "js/lucarne-main")
        await nc.ui.resources.delete_style("top_menu", "main", "css/lucarne")
        await nc.ui.top_menu.unregister("main")
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.create_directories()
    database.initialize()
    interrupted_downloads = media.recover_interrupted()
    if interrupted_downloads:
        logging.getLogger("lucarne.media").info("Marked %s interrupted download(s) as failed", interrupted_downloads)
    set_handlers(app, enabled_handler, map_app_static=False)
    agent.start()
    yield
    agent.stop()
    media.stop()


APP = FastAPI(title="Lucarne", version="1.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
APP.add_middleware(AppAPIAuthMiddleware)
for static_directory in ("js", "css", "img"):
    APP.mount(
        f"/{static_directory}",
        StaticFiles(directory=APPLICATION_ROOT / "static" / static_directory),
        name=static_directory,
    )


def user_id(nc: AsyncNextcloudApp) -> str:
    # AppAPI already validated and injected the acting user when it created this
    # request-scoped client. Reading the session value avoids another OCS call.
    value = nc._session._user  # noqa: SLF001
    if not value:
        raise LucarneError("An authenticated Nextcloud user is required.")
    return value


async def require_admin(nc: AsyncNextcloudApp) -> None:
    try:
        current_user = await nc.users.get_user()
    except Exception as error:
        raise HTTPException(status_code=403, detail="Administrator privileges are required.") from error
    if "admin" not in current_user.groups:
        raise HTTPException(status_code=403, detail="Administrator privileges are required.")


@APP.exception_handler(NotFoundError)
async def not_found_handler(request: Request, error: NotFoundError) -> JSONResponse:
    language = language_from_header(request.headers.get("accept-language"))
    return JSONResponse({"error": translate(language, str(error))}, status_code=404)


@APP.exception_handler(ConflictError)
async def conflict_handler(request: Request, error: ConflictError) -> JSONResponse:
    language = language_from_header(request.headers.get("accept-language"))
    return JSONResponse({"error": translate(language, str(error))}, status_code=409)


async def domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    language = language_from_header(request.headers.get("accept-language"))
    return JSONResponse({"error": translate(language, str(error))}, status_code=400)


APP.add_exception_handler(LucarneError, domain_error_handler)
APP.add_exception_handler(ValueError, domain_error_handler)


def present_channel(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["image_url"] = f"media/assets/channel/{row['id']}" if row.get("image_file") else None
    return result


def present_playlist(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["image_url"] = (
        f"media/assets/playlist/{row['id']}" if row.get("image_file") or row.get("cover_file") else None
    )
    return result


def present_video(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["thumbnail_url"] = f"media/assets/thumbnail/{row['id']}" if row.get("thumbnail_file") else None
    retained_media = database.one(
        """SELECT * FROM downloads WHERE user_id=? AND video_id=? AND retained=1 AND status='ready'
           ORDER BY updated_at DESC LIMIT 1""",
        (row["user_id"], row["id"]),
    )
    result["media_available"] = bool(retained_media and media.path_for(retained_media).is_file())
    result["media_retained"] = result["media_available"]
    result["media_mode"] = retained_media.get("mode") if retained_media else None
    return result


@APP.get("/api/bootstrap")
async def bootstrap(request: Request, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    uid = user_id(nc)
    try:
        current_user = await nc.users.get_user()
        is_admin = "admin" in current_user.groups
    except Exception:
        is_admin = False
    language = language_from_header(request.headers.get("accept-language"))
    return {
        "user_id": uid,
        "is_admin": is_admin,
        "language": language,
        "translations": catalog(language),
        "personal_settings": repository.personal_settings(uid),
        "catalogs": repository.catalogs(uid),
    }


@APP.get("/api/catalog")
async def get_catalog(
    nc: Annotated[AsyncNextcloudApp, Depends(anc_app)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    channel_id: int | None = None,
    playlist_id: int | None = None,
    catalog_id: int | None = None,
    uncategorized: bool = False,
    search: str = Query(default="", max_length=200),
) -> dict[str, Any]:
    uid = user_id(nc)
    pending: list[dict[str, Any]] = []
    if not search.strip() and channel_id is None and catalog_id is None:
        if playlist_id is not None:
            pending = repository.pending_video_jobs(uid, playlist_id)
        elif uncategorized:
            pending = repository.pending_video_jobs(uid, 0)
        else:
            pending = repository.pending_video_jobs(uid)
    data = repository.videos(
        uid, page, channel_id, playlist_id, catalog_id, uncategorized, search, pending_count=len(pending), page_size=page_size
    )
    data["items"] = [present_video(item) for item in data["items"]]
    offset = (page - 1) * page_size
    data["pending_jobs"] = pending[offset : offset + page_size]
    return data


@APP.get("/api/channels")
async def get_channels(
    nc: Annotated[AsyncNextcloudApp, Depends(anc_app)], catalog_id: int | None = None, uncategorized: bool = False
) -> list[dict[str, Any]]:
    return [present_channel(item) for item in repository.channels(user_id(nc), catalog_id, uncategorized)]


@APP.post("/api/channels", status_code=202)
async def add_channel(payload: UrlPayload, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    uid = user_id(nc)
    source_url = normalize_channel_url(payload.url)
    existing = repository.channel_by_source_url(uid, source_url)
    was_subscribed = bool(existing and existing["subscribed"] and not existing["deleting"])
    channel = repository.create_channel(uid, source_url)
    if str(channel.get("external_id") or "").startswith("pending_"):
        repository.enqueue(uid, "initialize_channel", "channel", int(channel["id"]), manual=True)
    elif not was_subscribed:
        repository.enqueue(
            uid,
            "sync_source",
            "channel",
            int(channel["id"]),
            {"source_type": "channel", "source_id": int(channel["id"])},
            manual=True,
        )
    return present_channel(channel)


@APP.get("/api/channels/{channel_id}")
async def get_channel(channel_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    return present_channel(repository.channel(user_id(nc), channel_id))


@APP.put("/api/channels/{channel_id}")
async def update_channel(
    channel_id: int, payload: PlaybackUpdate, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return present_channel(repository.update_channel(user_id(nc), channel_id, payload.model_dump()))


@APP.delete("/api/channels/{channel_id}", status_code=202)
async def delete_channel(
    channel_id: int, payload: DeleteRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, bool]:
    uid = user_id(nc)
    repository.mark_channel_deleting(uid, channel_id)
    repository.enqueue(uid, "delete_channel", "channel", channel_id, payload.model_dump(), manual=True)
    return {"queued": True}


@APP.get("/api/videos/{video_id}")
async def get_video(
    video_id: int,
    nc: Annotated[AsyncNextcloudApp, Depends(anc_app)],
    playlist_id: int | None = None,
) -> dict[str, Any]:
    uid = user_id(nc)
    video = repository.video(uid, video_id)
    result = present_video(video)
    parent: dict[str, Any] = {}
    if playlist_id is not None:
        try:
            parent = repository.playlist(uid, playlist_id)
        except NotFoundError:
            parent = {}
    if not parent and video.get("channel_id"):
        try:
            parent = repository.channel(uid, int(video["channel_id"]))
        except NotFoundError:
            parent = {}
    personal = repository.personal_settings(uid)
    result["inherited"] = {
        "mode": parent.get("mode") or personal["default_mode"],
        "quality": parent.get("quality") or personal["default_quality"],
        "audio_quality": parent.get("audio_quality") or personal["default_audio_quality"],
    }
    playback = media.playback_settings(uid, video, playlist_id)
    cached = media.cached_download(uid, video_id, playback)
    result["media_available"] = cached is not None
    result["media_retained"] = bool(cached and cached.get("retained"))
    result["media_mode"] = cached.get("mode") if cached else None
    return result


@APP.post("/api/videos", status_code=202)
async def add_video(payload: UrlPayload, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    uid = user_id(nc)
    job = repository.enqueue(uid, "inspect_video", "video", None, {"url": normalize_video_url(payload.url)}, True)
    return {"queued": True, "job": job}


@APP.put("/api/videos/{video_id}")
async def update_video(
    video_id: int, payload: PlaybackUpdate, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return present_video(repository.update_video_settings(user_id(nc), video_id, payload.model_dump()))


@APP.delete("/api/videos/{video_id}", status_code=202)
async def delete_video(video_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, bool]:
    uid = user_id(nc)
    repository.mark_video_deleting(uid, video_id)
    repository.enqueue(uid, "delete_video", "video", video_id, manual=True)
    return {"queued": True}


@APP.post("/api/videos/{video_id}/downloads", status_code=202)
async def create_download(
    video_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)], playlist_id: int | None = None
) -> dict[str, Any]:
    return media.create_download(user_id(nc), video_id, playlist_id)


@APP.get("/api/downloads/{download_id}")
async def get_download(
    download_id: str,
    request: Request,
    nc: Annotated[AsyncNextcloudApp, Depends(anc_app)],
) -> dict[str, Any]:
    result = media.download(user_id(nc), download_id)
    if result.get("error"):
        result["error"] = translate(language_from_header(request.headers.get("accept-language")), str(result["error"]))
    return result


@APP.put("/api/videos/{video_id}/retention")
async def retain_video(
    video_id: int, payload: RetentionRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return present_video(media.retain(user_id(nc), video_id, payload.retained))


@APP.get("/api/playlists")
async def get_playlists(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> list[dict[str, Any]]:
    return [present_playlist(item) for item in repository.playlists(user_id(nc))]


@APP.post("/api/playlists")
async def create_playlist(
    payload: PlaylistCreate, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return present_playlist(repository.create_playlist(user_id(nc), payload.title))


@APP.post("/api/playlists/import", status_code=202)
async def import_playlist(payload: UrlPayload, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    uid = user_id(nc)
    source_url = normalize_playlist_url(payload.url)
    existing = database.one("SELECT * FROM playlists WHERE user_id=? AND source_url=?", (uid, source_url))
    playlist = repository.create_playlist(uid, "Pending playlist", source_url)
    if existing is None or str(playlist.get("external_id") or "").startswith("pending_"):
        repository.enqueue(uid, "initialize_playlist", "playlist", int(playlist["id"]), manual=True)
    return present_playlist(playlist)


@APP.get("/api/playlists/{playlist_id}")
async def get_playlist(playlist_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    uid = user_id(nc)
    result = present_playlist(repository.playlist(uid, playlist_id))
    result["videos"] = [present_video(item) for item in repository.videos(uid, 1, playlist_id=playlist_id)["items"]]
    return result


@APP.put("/api/playlists/{playlist_id}")
async def update_playlist(
    playlist_id: int, payload: PlaylistUpdate, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return present_playlist(repository.update_playlist(user_id(nc), playlist_id, payload.model_dump()))


@APP.delete("/api/playlists/{playlist_id}", status_code=202)
async def delete_playlist(
    playlist_id: int, payload: DeleteRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, bool]:
    uid = user_id(nc)
    repository.mark_playlist_deleting(uid, playlist_id)
    repository.enqueue(uid, "delete_playlist", "playlist", playlist_id, payload.model_dump(), manual=True)
    return {"queued": True}


@APP.post("/api/playlists/{playlist_id}/videos", status_code=202)
async def add_playlist_video(
    playlist_id: int, payload: PlaylistVideoRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    uid = user_id(nc)
    if repository.playlist(uid, playlist_id)["kind"] != "personal":
        raise ConflictError("A YouTube playlist is managed by the collection agent.")
    if payload.video_id is not None:
        repository.attach_video(uid, playlist_id, payload.video_id)
        return {"queued": False}
    if not payload.url:
        raise ValueError("A video identifier or URL is required.")
    job = repository.enqueue(
        uid,
        "inspect_video",
        "playlist",
        playlist_id,
        {"url": normalize_video_url(payload.url), "playlist_id": playlist_id},
        True,
    )
    return {"queued": True, "job": job}


@APP.delete("/api/playlists/{playlist_id}/videos/{video_id}")
async def remove_playlist_video(
    playlist_id: int, video_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, bool]:
    uid = user_id(nc)
    if repository.playlist(uid, playlist_id)["kind"] != "personal":
        raise ConflictError("A YouTube playlist is managed by the collection agent.")
    repository.detach_video(uid, playlist_id, video_id)
    return {"deleted": True}


@APP.get("/api/catalogs")
async def get_catalogs(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> list[dict[str, Any]]:
    return repository.catalogs(user_id(nc))


@APP.get("/api/catalogs/{catalog_id}")
async def get_channel_catalog(catalog_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    return repository.catalog(user_id(nc), catalog_id)


@APP.post("/api/catalogs")
async def create_catalog(payload: CatalogRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    return repository.create_catalog(user_id(nc), payload.name)


@APP.put("/api/catalogs/{catalog_id}")
async def update_catalog(
    catalog_id: int, payload: CatalogRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return repository.update_catalog(user_id(nc), catalog_id, payload.name)


@APP.put("/api/catalogs/{catalog_id}/channels")
async def replace_catalog_channels(
    catalog_id: int, payload: CatalogChannelsRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return repository.replace_catalog_channels(user_id(nc), catalog_id, payload.channel_ids)


@APP.delete("/api/catalogs/{catalog_id}")
async def delete_catalog(catalog_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, bool]:
    repository.delete_catalog(user_id(nc), catalog_id)
    return {"deleted": True}


@APP.get("/api/history")
async def get_history(
    nc: Annotated[AsyncNextcloudApp, Depends(anc_app)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    result = repository.history(user_id(nc), page, page_size)
    result["items"] = [present_video(item) for item in result["items"]]
    return result


@APP.put("/api/history/{video_id}")
async def save_history(
    video_id: int, payload: HistoryRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, bool]:
    repository.save_history(user_id(nc), video_id, payload.position, payload.duration)
    return {"saved": True}


@APP.delete("/api/history")
async def clear_history(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, bool]:
    repository.clear_history(user_id(nc))
    return {"deleted": True}


@APP.delete("/api/history/{video_id}")
async def delete_history(video_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, bool]:
    repository.clear_history(user_id(nc), video_id)
    return {"deleted": True}


@APP.get("/api/settings/personal")
async def get_personal_settings(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    return repository.personal_settings(user_id(nc))


@APP.put("/api/settings/personal")
async def update_personal_settings(
    payload: PersonalSettingsRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    return repository.update_personal_settings(user_id(nc), payload.model_dump())


@APP.get("/api/agent")
async def get_agent(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    await require_admin(nc)
    return repository.agent_status(user_id(nc))


@APP.get("/api/schedule")
async def get_agent_schedule(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, int]:
    status = repository.agent_status(user_id(nc))
    return {
        "next_lot_at": int(status["campaign"]["next_lot_at"]),
        "server_time": int(status["server_time"]),
    }


@APP.post("/api/agent/jobs/{job_id}/retry")
async def retry_job(job_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    await require_admin(nc)
    return repository.retry_job(user_id(nc), job_id)


@APP.post("/api/agent/jobs/{job_id}/move")
async def move_job(
    job_id: int, payload: MoveRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    await require_admin(nc)
    return repository.move_job(user_id(nc), job_id, payload.direction)


@APP.delete("/api/agent/jobs/{job_id}")
async def delete_job(job_id: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, bool]:
    await require_admin(nc)
    repository.delete_job(user_id(nc), job_id)
    return {"deleted": True}


@APP.get("/api/admin/settings")
async def get_admin_settings(nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> dict[str, Any]:
    await require_admin(nc)
    return repository.instance_settings()


@APP.put("/api/admin/settings")
async def update_admin_settings(
    payload: InstanceSettingsRequest, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]
) -> dict[str, Any]:
    await require_admin(nc)
    result = repository.update_instance_settings(payload.model_dump())
    repository.apply_instance_settings()
    return result


def asset_path(kind: str, uid: str, identifier: int) -> Path:
    if kind == "thumbnail":
        row = repository.video(uid, identifier)
        return settings.thumbnails / str(row.get("thumbnail_file") or "")
    if kind == "channel":
        row = repository.channel(uid, identifier)
        return settings.channel_images / str(row.get("image_file") or "")
    if kind == "playlist":
        row = repository.playlist(uid, identifier)
        if row.get("image_file"):
            return settings.playlist_images / str(row["image_file"])
        first = database.one(
            """SELECT v.thumbnail_file FROM playlist_videos pv JOIN videos v ON v.id=pv.video_id
               WHERE pv.playlist_id=? AND v.user_id=? ORDER BY pv.position,pv.added_at LIMIT 1""",
            (identifier, uid),
        )
        return settings.thumbnails / str((first or {}).get("thumbnail_file") or "")
    raise NotFoundError("Asset not found.")


@APP.get("/media/assets/{kind}/{identifier}")
async def get_asset(kind: str, identifier: int, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> FileResponse:
    path = asset_path(kind, user_id(nc), identifier)
    allowed_parents = {settings.thumbnails, settings.channel_images, settings.playlist_images}
    if not path.is_file() or path.parent not in allowed_parents:
        raise NotFoundError("Asset not found.")
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@APP.get("/media/downloads/{download_id}")
async def stream_media(download_id: str, nc: Annotated[AsyncNextcloudApp, Depends(anc_app)]) -> FileResponse:
    row = media.download(user_id(nc), download_id)
    if row["status"] != "ready":
        raise ConflictError("The media is not ready.")
    path = media.path_for(row)
    if not path.is_file():
        raise NotFoundError("Media file not found.")
    timestamp = int(time.time())
    with database.write() as connection:
        connection.execute(
            "UPDATE downloads SET accessed_at=?,updated_at=? WHERE id=?", (timestamp, timestamp, download_id)
        )
    return FileResponse(path, media_type=row.get("mime_type") or "application/octet-stream")


if __name__ == "__main__":
    os.chdir("/app")
    run_app("src.main:APP", log_level=os.getenv("UVICORN_LOG_LEVEL", "info"))
