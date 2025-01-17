import asyncio
import logging

from sqlalchemy.orm import close_all_sessions

from common.config.parser.logging_config import setup_logging
from common.factory import create_telegraph, create_dataclass_factory
from infrastructure.clients.factory import create_file_storage
from infrastructure.db.faсtory import create_pool, create_lock_factory, create_level_test_dao
from infrastructure.scheduler.factory import create_scheduler
from tgbot.config.parser.main import load_config
from tgbot.main_factory import (
    create_bot,
    create_dispatcher,
    get_paths,
    create_redis,
)
from tgbot.username_resolver.user_getter import UserGetter
from tgbot.views.jinja_filters import setup_jinja

logger = logging.getLogger(__name__)


async def main():
    paths = get_paths()

    setup_logging(paths)
    config = load_config(paths)
    dcf = create_dataclass_factory()
    file_storage = create_file_storage(config.file_storage_config)
    pool = create_pool(config.db)
    bot = create_bot(config)
    setup_jinja(bot=bot)
    level_test_dao = create_level_test_dao()

    async with (
        UserGetter(config.tg_client) as user_getter,
        create_redis(config.redis) as redis,
        create_scheduler(
            pool=pool,
            redis=redis,
            bot=bot,
            redis_config=config.redis,
            game_log_chat=config.bot.log_chat,
            file_storage=file_storage,
            level_test_dao=level_test_dao,
        ) as scheduler,
    ):
        dp = create_dispatcher(
            config=config,
            user_getter=user_getter,
            dcf=dcf,
            pool=pool,
            redis=redis,
            scheduler=scheduler,
            locker=create_lock_factory(),
            file_storage=file_storage,
            level_test_dao=level_test_dao,
            telegraph=create_telegraph(config.bot),
        )

        logger.info("started")
        try:
            await dp.start_polling(bot)
        finally:
            close_all_sessions()
            await bot.session.close()
            await redis.close()
            logger.info("stopped")


if __name__ == "__main__":
    asyncio.run(main())
