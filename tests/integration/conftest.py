import logging
import os
from typing import Generator, AsyncGenerator

import pytest
import pytest_asyncio
from aiogram import Dispatcher, Bot
from aiogram_dialog.test_tools import MockMessageManager
from aiogram_tests.mocked_bot import MockedBot
from alembic.command import upgrade
from alembic.config import Config as AlembicConfig
from dataclass_factory import Factory
from mockito import mock
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, close_all_sessions
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from common.config.models.paths import Paths
from common.factory import create_telegraph
from infrastructure.clients.file_gateway import BotFileGateway
from infrastructure.db.config.models.db import RedisConfig
from infrastructure.db.dao.holder import HolderDao
from infrastructure.db.dao.memory.level_testing import LevelTestingData
from infrastructure.db.faсtory import create_lock_factory, create_level_test_dao
from shvatka.interfaces.clients.file_storage import FileStorage, FileGateway
from shvatka.interfaces.scheduler import Scheduler
from shvatka.utils.key_checker_lock import KeyCheckerFactory
from tests.fixtures.conftest import fixtures_resource_path  # noqa: F401
from tests.fixtures.game_fixtures import game, finished_game  # noqa: F401
from tests.fixtures.player import harry, hermione, ron, author, draco  # noqa: F401
from tests.fixtures.scn_fixtures import simple_scn, complex_scn, three_lvl_scn  # noqa: F401
from tests.fixtures.team import gryffindor, slytherin  # noqa: F401
from tests.mocks.config import DBConfig
from tests.mocks.file_storage import MemoryFileStorage
from tests.mocks.scheduler_mock import SchedulerMock
from tgbot.config.models.main import TgBotConfig
from tgbot.handlers import setup_handlers
from tgbot.main_factory import (
    create_redis,
    create_only_dispatcher,
)
from tgbot.middlewares import setup_middlewares
from tgbot.username_resolver.user_getter import UserGetter
from tgbot.views.hint_factory.hint_parser import HintParser
from tgbot.views.telegraph import Telegraph

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def level_test_dao() -> LevelTestingData:
    return create_level_test_dao()


@pytest_asyncio.fixture
async def dao(session: AsyncSession, redis: Redis, level_test_dao: LevelTestingData) -> HolderDao:
    dao_ = HolderDao(session=session, redis=redis, level_test=level_test_dao)
    await clear_data(dao_)
    return dao_


@pytest_asyncio.fixture
async def check_dao(
    session: AsyncSession, redis: Redis, level_test_dao: LevelTestingData
) -> HolderDao:
    dao_ = HolderDao(session=session, redis=redis, level_test=level_test_dao)
    return dao_


async def clear_data(dao: HolderDao):
    await dao.poll.delete_all()
    await dao.achievement.delete_all()
    await dao.file_info.delete_all()
    await dao.organizer.delete_all()
    await dao.waiver.delete_all()
    await dao.level.delete_all()
    await dao.level_time.delete_all()
    await dao.key_time.delete_all()
    await dao.game.delete_all()
    await dao.team_player.delete_all()
    await dao.chat.delete_all()
    await dao.team.delete_all()
    await dao.user.delete_all()
    await dao.player.delete_all()
    await dao.commit()


@pytest_asyncio.fixture
async def session(pool: sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    async with pool() as session_:
        yield session_


@pytest.fixture(scope="session")
def pool(postgres_url: str) -> Generator[sessionmaker, None, None]:
    engine = create_async_engine(url=postgres_url)
    pool_ = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    yield pool_
    close_all_sessions()


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    postgres = PostgresContainer("postgres:11")
    if os.name == "nt":  # TODO workaround from testcontainers/testcontainers-python#108
        postgres.get_container_host_ip = lambda: "localhost"
    try:
        postgres.start()
        postgres_url_ = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        logger.info("postgres url %s", postgres_url_)
        yield postgres_url_
    finally:
        postgres.stop()


@pytest.fixture(scope="session")
def redis() -> Generator[Redis, None, None]:
    redis_container = RedisContainer("redis:latest")
    if os.name == "nt":  # TODO workaround from testcontainers/testcontainers-python#108
        redis_container.get_container_host_ip = lambda: "localhost"
    try:
        redis_container.start()
        url = redis_container.get_container_host_ip()
        port = redis_container.get_exposed_port(redis_container.port_to_expose)
        r = create_redis(
            RedisConfig(
                url=url,
                port=int(port),
            )
        )
        yield r
    finally:
        redis_container.stop()


@pytest.fixture(autouse=True)
def patch_api_config(bot_config: TgBotConfig, postgres_url: str, redis: Redis):
    bot_config.db = DBConfig(postgres_url)  # type: ignore
    bot_config.redis.url = redis.connection_pool.connection_kwargs["host"]
    bot_config.redis.port = redis.connection_pool.connection_kwargs["port"]
    bot_config.redis.db = redis.connection_pool.connection_kwargs["db"]


@pytest_asyncio.fixture(scope="session")
async def scheduler():
    return SchedulerMock()


@pytest.fixture(scope="session")
def locker() -> KeyCheckerFactory:
    return create_lock_factory()


@pytest.fixture(scope="session")
def telegraph(bot_config: TgBotConfig) -> Telegraph:
    return create_telegraph(bot_config=bot_config.bot)


@pytest.fixture(scope="session")
def message_manager():
    return MockMessageManager()


@pytest.fixture(scope="session")
def dp(
    pool: sessionmaker,
    bot_config: TgBotConfig,
    user_getter: UserGetter,
    dcf: Factory,
    redis: Redis,
    scheduler: Scheduler,
    locker: KeyCheckerFactory,
    file_storage: FileStorage,
    level_test_dao: LevelTestingData,
    telegraph: Telegraph,
    message_manager: MockMessageManager,
) -> Dispatcher:
    dp = create_only_dispatcher(bot_config, redis)
    setup_middlewares(
        dp=dp,
        pool=pool,
        bot_config=bot_config.bot,
        user_getter=user_getter,
        dcf=dcf,
        redis=redis,
        scheduler=scheduler,
        locker=locker,
        file_storage=file_storage,
        level_test_dao=level_test_dao,
        telegraph=telegraph,
    )
    setup_handlers(dp, bot_config.bot, dict(message_manager=message_manager))
    return dp


@pytest.fixture(scope="session")
def user_getter() -> UserGetter:
    dummy = mock(UserGetter)
    return dummy


@pytest.fixture
def bot(bot_config: TgBotConfig):
    bot = MockedBot(token=bot_config.bot.token)
    return bot


@pytest.fixture(scope="session")
def alembic_config(postgres_url: str, paths: Paths) -> AlembicConfig:
    alembic_cfg = AlembicConfig(str(paths.app_dir.parent / "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location", str(paths.app_dir.parent / "infrastructure" / "db" / "migrations")
    )
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_url)
    return alembic_cfg


@pytest.fixture(scope="session", autouse=True)
def upgrade_schema_db(alembic_config: AlembicConfig):
    upgrade(alembic_config, "head")


@pytest.fixture(scope="session")
def file_storage() -> FileStorage:
    return MemoryFileStorage()


@pytest.fixture
def hint_parser(
    dao: HolderDao,
    file_storage: FileStorage,
    bot: Bot,
) -> HintParser:
    return HintParser(dao=dao.file_info, file_storage=file_storage, bot=bot)


@pytest.fixture
def file_gateway(file_storage: FileStorage, bot: Bot, hint_parser: HintParser) -> FileGateway:
    return BotFileGateway(
        bot=bot,
        file_storage=file_storage,
        hint_parser=hint_parser,
    )


@pytest.fixture(autouse=True)
def clean_up_memory(file_storage: MemoryFileStorage):
    file_storage.storage.clear()
