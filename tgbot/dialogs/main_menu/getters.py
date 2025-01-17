from aiogram_dialog import DialogManager

from infrastructure.db.dao.holder import HolderDao
from shvatka.models import dto
from shvatka.services.organizers import get_by_player_or_none
from shvatka.services.player import save_promotion_invite
from tgbot import keyboards as kb


async def get_main(dao: HolderDao, player: dto.Player, game: dto.Game, **_):
    if game:
        org = await get_by_player_or_none(player=player, game=game, dao=dao.organizer)
    else:
        org = None
    return {
        "player": player,
        "game": game,
        "org": org,
    }


async def get_promotion_token(dialog_manager: DialogManager, **_):
    dao: HolderDao = dialog_manager.middleware_data["dao"]
    player: dto.Player = dialog_manager.middleware_data["player"]
    token = await save_promotion_invite(player, dao.secure_invite)
    return {
        "player": player,
        "inline_query": kb.PromotePlayerID(token=token).pack(),
    }
