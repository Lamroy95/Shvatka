from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from db import models
from shvatka.models import dto
from shvatka.models.dto.scn.game import GameScenario
from shvatka.models.enums import GameStatus
from shvatka.models.enums.game_status import ACTIVE_STATUSES
from shvatka.utils.datetime_utils import tz_utc
from shvatka.utils.exceptions import GameHasAnotherAuthor
from .base import BaseDAO


class GameDao(BaseDAO[models.Game]):
    def __init__(self, session: AsyncSession):
        super().__init__(models.Game, session)

    async def upsert_game(
        self,
        author: dto.Player,
        scn: GameScenario,
    ) -> dto.Game:
        try:
            game = await self.get_by_author_and_scn(author, scn)
        except NoResultFound:
            game = models.Game(
                author_id=author.id,
                name=scn.name,
                status=GameStatus.underconstruction,
            )
            self._save(game)
        await self._flush(game)
        return game.to_dto(author)

    async def get_by_author_and_scn(self, author: dto.Player, scn: GameScenario) -> models.Game:
        result = await self.session.execute(
            select(models.Game).where(
                models.Game.name == scn.name,
                models.Game.author_id == author.id,
            )
        )
        return result.scalar_one()

    async def get_full(self, id_: int) -> dto.FullGame:
        result = await self.session.execute(
            select(models.Game)
            .options(
                joinedload(models.Game.levels),
                joinedload(models.Game.author)
                .joinedload(models.Player.user)
            )
            .where(models.Game.id == id_)
        )
        game_db: models.Game = result.unique().scalar_one()
        author = game_db.author.to_dto_user_prefetched()
        return game_db.to_full_dto(
            author=author,
            levels=[level.to_dto(author) for level in game_db.levels],
        )

    async def get_by_id(self, id_: int, author: dto.Player | None = None) -> dto.Game:
        if not author:
            options = [joinedload(models.Game.author).joinedload(models.Player.user)]
            game = await self._get_by_id(id_, options)
            author = game.author.to_dto_user_prefetched()
        else:
            game = await self._get_by_id(id_)
            if author and game.author_id != author.id:
                raise GameHasAnotherAuthor(game_id=game.id, player=author)
        return game.to_dto(author)

    async def get_all_by_author(self, author: dto.Player) -> list[dto.Game]:
        result = await self.session.execute(
            select(models.Game).where(
                models.Game.author_id == author.id,
                models.Game.status != GameStatus.complete,
            )
        )
        games = result.scalars().all()
        return [game.to_dto(author) for game in games]

    async def start_waivers(self, game: dto.Game):
        await self.set_status(game, GameStatus.getting_waivers)

    async def start(self, game: dto.Game):
        await self.set_status(game, GameStatus.started)

    async def set_status(self, game: dto.Game, status: GameStatus):
        await self.session.execute(
            update(models.Game)
            .where(models.Game.id == game.id)
            .values(status=status)
        )

    async def get_active_game(self) -> dto.Game | None:
        result = await self.session.execute(
            select(models.Game)
            .where(models.Game.status.in_(ACTIVE_STATUSES))
            .options(
                joinedload(models.Game.author)
                .joinedload(models.Player.user)
            )
        )
        try:
            game: models.Game = result.scalar_one()
        except NoResultFound:
            return None
        return game.to_dto(
            game.author.to_dto_user_prefetched()
        )

    async def create_game(self, author: dto.Player, name: str) -> dto.Game:
        game_db = models.Game(
            author_id=author.id,
            name=name,
            status=GameStatus.underconstruction,
        )
        self._save(game_db)
        await self._flush(game_db)
        return game_db.to_dto(author)

    async def set_start_at(self, game: dto.Game, start_at: datetime):
        await self.session.execute(
            update(models.Game)
            .where(models.Game.id == game.id)
            .values(start_at=start_at.astimezone(tz_utc))
        )

    async def set_started(self, game: dto.Game):
        await self.set_status(game, GameStatus.started)

    async def set_finished(self, game: dto.Game):
        await self.set_status(game, GameStatus.finished)

    async def is_name_available(self, name: str) -> bool:
        return not bool(await self._get_game_by_name(name))

    async def is_author_game_by_name(self, name: str, author: dto.Player) -> bool:
        result = await self._get_game_by_name(name)
        if result.author_id != author.id:
            return False
        return True

    async def _get_game_by_name(self, name: str) -> models.Game | None:
        result = await self.session.execute(
            select(models.Game)
            .where(models.Game.name == name)
        )
        return result.scalar_one_or_none()
