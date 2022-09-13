import asyncio
import logging

import dataclass_factory
from sqlalchemy.orm import close_all_sessions

from app.config import load_config
from app.config.logging_config import setup_logging
from app.dao.redis.base import create_redis
from app.models.db import create_pool
from app.models.schems import schemas
from app.services.username_resolver.user_getter import UserGetter
from tgbot.main_factory import create_bot, create_dispatcher, get_paths, create_scheduler

logger = logging.getLogger(__name__)


async def main():
    paths = get_paths()

    setup_logging(paths)
    config = load_config(paths)
    dcf = dataclass_factory.Factory(schemas=schemas)
    pool = create_pool(config.db)
    bot = create_bot(config)

    async with (
        UserGetter(config.tg_client) as user_getter,
        create_redis(config.redis) as redis,
        create_scheduler(
            pool=pool, redis=redis, bot=bot, redis_config=config.redis,
        ) as scheduler,
    ):
        dp = create_dispatcher(
            config=config, user_getter=user_getter, dcf=dcf, pool=pool,
            redis=redis, scheduler=scheduler,
        )

        logger.info("started")
        try:
            await dp.start_polling(bot)
        finally:
            close_all_sessions()
            await bot.session.close()
            await redis.close()
            logger.info("stopped")


if __name__ == '__main__':
    asyncio.run(main())