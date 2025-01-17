from typing import Protocol

from shvatka.interfaces.dal.base import Committer
from shvatka.models import dto
from shvatka.models.dto import scn


class LevelUpserter(Committer, Protocol):
    async def upsert(
        self,
        author: dto.Player,
        scenario: scn.LevelScenario,
        game: dto.Game = None,
        no_in_game: int = None,
    ) -> dto.Level:
        raise NotImplementedError

    async def unlink_all(self, game: dto.Game) -> None:
        raise NotImplementedError


class MyLevelsGetter(Protocol):
    async def get_all_my(self, author: dto.Player) -> list[dto.Level]:
        raise NotImplementedError


class LevelByIdGetter(Protocol):
    async def get_by_id(self, id_: int) -> dto.Level:
        raise NotImplementedError


class LevelLinker(Committer, Protocol):
    async def link_to_game(self, level: dto.Level, game: dto.Game) -> dto.Level:
        raise NotImplementedError
