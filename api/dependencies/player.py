from fastapi.params import Depends

from api.dependencies import dao_provider, get_current_user
from infrastructure.db.dao.holder import HolderDao
from shvatka.models import dto
from shvatka.services.player import upsert_player


def player_provider() -> dto.Player:
    raise NotImplementedError


async def db_player_provider(
    dao: HolderDao = Depends(dao_provider),  # type: ignore[assignment]
    user: dto.User = Depends(get_current_user),  # type: ignore[assignment]
) -> dto.Player:
    return await upsert_player(user, dao.player)
