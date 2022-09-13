from typing import Any, Union, Dict

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.models import dto
from app.models.enums import GameStatus


class GameStatusFilter(BaseFilter):
    active: bool | None = None
    running: bool | None = None
    status: GameStatus | None = None

    async def __call__(self, message: Message, game: dto.Game) -> Union[bool, Dict[str, Any]]:
        if self.active is not None:
            return self.check_active(game)
        if self.running is not None:
            return self.check_running(game)
        if self.status is not None:
            return self.check_by_status(game)

    def check_active(self, game: dto.Game) -> bool:
        if game is not None and game.is_active():
            return self.active
        return not self.active

    def check_running(self, game: dto.Game) -> bool:
        if game is not None and game.is_started():
            return self.running
        return not self.running

    def check_by_status(self, game: dto.Game) -> bool:
        if game is None:
            return False
        return game.status == self.status