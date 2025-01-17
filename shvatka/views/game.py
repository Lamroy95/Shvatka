from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, Iterable

from shvatka.interfaces.dal.game_play import GamePreparer
from shvatka.models import dto


class GameViewPreparer(Protocol):
    async def prepare_game_view(
        self,
        game: dto.Game,
        teams: Iterable[dto.Team],
        orgs: Iterable[dto.Organizer],
        dao: GamePreparer,
    ) -> None:
        raise NotImplementedError


class GameView(Protocol):
    async def send_puzzle(self, team: dto.Team, level: dto.Level) -> None:
        raise NotImplementedError

    async def send_hint(self, team: dto.Team, hint_number: int, level: dto.Level) -> None:
        raise NotImplementedError

    async def duplicate_key(self, key: dto.KeyTime) -> None:
        raise NotImplementedError

    async def correct_key(self, key: dto.KeyTime) -> None:
        raise NotImplementedError

    async def wrong_key(self, key: dto.KeyTime) -> None:
        raise NotImplementedError

    async def game_finished(self, team: dto.Team) -> None:
        raise NotImplementedError

    async def game_finished_by_all(self, team: dto.Team) -> None:
        raise NotImplementedError


class GameLogWriter(Protocol):
    async def log(self, message: str) -> None:
        raise NotImplementedError


class OrgNotifier(Protocol):
    async def notify(self, event: Event) -> None:
        raise NotImplementedError


@dataclass
class Event:
    orgs_list: list[dto.Organizer]


@dataclass
class LevelUp(Event):
    team: dto.Team
    new_level: dto.Level


@dataclass
class NewOrg(Event):
    game: dto.Game
    org: dto.SecondaryOrganizer


@dataclass
class LevelTestCompleted(Event):
    suite: dto.LevelTestSuite
    result: timedelta
