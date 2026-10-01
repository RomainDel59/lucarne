"""Default language of the YouTube metadata, taken from the first Nextcloud administrator."""

from __future__ import annotations

import logging
from typing import Any

from .localization import language_from_header

LOGGER = logging.getLogger(__name__)


async def first_administrator_language(nc: Any) -> str | None:
    """Return the supported language of the first administrator, or None when Nextcloud does not tell.

    Only an administrator may list the administrator group, so this works for requests made by one.
    """
    try:
        members = (await nc.ocs("GET", "/ocs/v2.php/cloud/groups/admin/users")).get("users") or []
        if not members:
            return None
        return language_from_header((await nc.users.get_user(str(members[0]))).language)
    except Exception as error:
        LOGGER.info("Could not read the language of the first administrator: %s", error)
        return None
