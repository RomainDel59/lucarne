"""When to try again a video that could not be read."""

from src.skipped import DEFAULT_RELEASE_DELAY, GIVE_UP_AFTER, RELEASE_MARGIN, UNKNOWN_RETRY_DELAYS, schedule

NOW = 1_800_000_000


def failure(**values: object) -> dict:
    return {"id": "video12345", "reason": "x", "known": False, "temporary": False, "retry_after": None, **values}


def test_a_known_permanent_cause_is_never_tried_again() -> None:
    assert schedule(failure(known=True), 0, NOW, NOW) == (1, None)


def test_an_unknown_cause_is_tried_three_times_in_total_at_growing_intervals() -> None:
    attempts, retry_at = schedule(failure(), 0, NOW, NOW)
    assert (attempts, retry_at) == (1, NOW + UNKNOWN_RETRY_DELAYS[0])
    attempts, retry_at = schedule(failure(), attempts, NOW, NOW)
    assert (attempts, retry_at) == (2, NOW + UNKNOWN_RETRY_DELAYS[1])
    assert schedule(failure(), attempts, NOW, NOW) == (3, None)


def test_a_premiere_with_a_known_start_is_tried_again_just_after_it() -> None:
    result = schedule(failure(known=True, temporary=True, retry_after=7200), 0, NOW, NOW)

    assert result == (1, NOW + 7200 + RELEASE_MARGIN)


def test_a_premiere_without_a_start_is_looked_at_every_hour_for_a_week() -> None:
    first = failure(known=True, temporary=True)

    assert schedule(first, 0, NOW, NOW) == (1, NOW + DEFAULT_RELEASE_DELAY)
    assert schedule(first, 5, NOW, NOW + GIVE_UP_AFTER - 1) == (6, NOW + GIVE_UP_AFTER - 1 + DEFAULT_RELEASE_DELAY)
    assert schedule(first, 5, NOW, NOW + GIVE_UP_AFTER) == (6, None)


def test_a_premiere_announced_far_away_is_not_given_up_after_a_week() -> None:
    far = failure(known=True, temporary=True, retry_after=20 * 86400)

    assert schedule(far, 0, NOW, NOW + GIVE_UP_AFTER)[1] == NOW + GIVE_UP_AFTER + 20 * 86400 + RELEASE_MARGIN
