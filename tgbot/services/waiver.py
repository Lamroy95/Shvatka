from aiogram.types import Message

from infrastructure.db.dao import PollDao
from shvatka.models import dto


async def swap_saved_message(game: dto.Game, msg: Message, dao: PollDao):
    old_msg_id = await dao.get_pool_msg_id(chat_id=msg.chat.id, game_id=game.id)
    await dao.save_pool_msg_id(chat_id=msg.chat.id, game_id=game.id, msg_id=msg.message_id)
    return old_msg_id


async def get_saved_message(game: dto.Game, team: dto.Team, dao: PollDao) -> int:
    return await dao.get_pool_msg_id(chat_id=team.chat.tg_id, game_id=game.id)
