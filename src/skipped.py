"""When to try again a video that could not be read."""

from __future__ import annotations

from typing import Any

# After the first failure of a video whose cause is unknown, then after the second one. The third is final.
UNKNOWN_RETRY_DELAYS = (3600, 6 * 3600)
# A premiere or a live event with no announced time is looked at every hour, for at most a week.
DEFAULT_RELEASE_DELAY = 3600
GIVE_UP_AFTER = 7 * 86400
# Margin after an announced start, so that the video is readable when it is looked at.
RELEASE_MARGIN = 120


def schedule(failure: dict[str, Any], attempts: int, first_seen: int, current: int) -> tuple[int, int | None]:
    """Return the number of attempts made and the time of the next one, or None when the video is given up."""
    attempts += 1
    if failure.get("temporary"):
        delay = failure.get("retry_after")
        if delay is not None:
            return attempts, current + int(delay) + RELEASE_MARGIN
        if current - first_seen >= GIVE_UP_AFTER:
            return attempts, None
        return attempts, current + DEFAULT_RELEASE_DELAY
    if failure.get("known"):
        return attempts, None
    if attempts > len(UNKNOWN_RETRY_DELAYS):
        return attempts, None
    return attempts, current + UNKNOWN_RETRY_DELAYS[attempts - 1]
