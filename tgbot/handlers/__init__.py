import logging
from typing import Any

from aiogram import Dispatcher

from tgbot import dialogs
from tgbot.config.models.bot import BotConfig
from tgbot.handlers import base, game, waivers, player
from tgbot.handlers import errors
from tgbot.handlers import last
from tgbot.handlers import superuser
from tgbot.handlers import team

logger = logging.getLogger(__name__)


def setup_handlers(dp: Dispatcher, bot_config: BotConfig, registry_kwargs: dict[str, Any]):
    errors.setup(dp, bot_config.log_chat)
    dp.include_router(base.setup())
    dp.include_router(superuser.setup(bot_config))
    dp.include_router(player.setup())
    dp.include_router(team.setup())
    dp.include_router(game.setup())
    dp.include_router(waivers.setup())

    dialogs.setup(dp, registry_kwargs=registry_kwargs)

    # always must be last registered
    dp.include_router(last.setup())
    logger.debug("handlers configured successfully")
