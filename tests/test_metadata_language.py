"""Default metadata language tests."""

from types import SimpleNamespace
from typing import Any

from src.metadata_language import first_administrator_language


class FakeNextcloud:
    def __init__(self, members: list[str], languages: dict[str, str], error: Exception | None = None) -> None:
        self.members = members
        self.requested: list[str] = []
        self.error = error

        async def get_user(user_id: str) -> Any:
            self.requested.append(user_id)
            return SimpleNamespace(language=languages[user_id])

        self.users = SimpleNamespace(get_user=get_user)

    async def ocs(self, method: str, path: str) -> dict[str, list[str]]:
        if self.error:
            raise self.error
        assert (method, path) == ("GET", "/ocs/v2.php/cloud/groups/admin/users")
        return {"users": self.members}


async def test_the_language_of_the_first_administrator_is_used() -> None:
    nextcloud = FakeNextcloud(["root", "second"], {"root": "fr_FR", "second": "en"})

    assert await first_administrator_language(nextcloud) == "fr"
    assert nextcloud.requested == ["root"]


async def test_an_unsupported_language_falls_back_to_english() -> None:
    assert await first_administrator_language(FakeNextcloud(["root"], {"root": "de_DE"})) == "en"


async def test_nothing_is_returned_when_nextcloud_refuses_or_has_no_administrator() -> None:
    assert await first_administrator_language(FakeNextcloud(["root"], {}, PermissionError("403"))) is None
    assert await first_administrator_language(FakeNextcloud([], {})) is None
