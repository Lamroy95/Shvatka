import logging.config

import yaml

from shvatka.config.db import load_db_config, load_redis_config
from shvatka.config.storage import load_storage_config
from shvatka.models.config import Config
from shvatka.models.config.main import Paths, BotConfig, BotApiConfig, BotApiType, TgClientConfig

logger = logging.getLogger(__name__)


def load_config(paths: Paths) -> Config:
    with (paths.config_path / "config.yml").open("r") as f:
        config_dct = yaml.safe_load(f)

    bot_config = load_bot_config(config_dct["bot"])
    return Config(
        paths=paths,
        db=load_db_config(config_dct["db"]),
        bot=bot_config,
        storage=load_storage_config(config_dct["storage"]),
        tg_client=TgClientConfig(bot_token=bot_config.token),
        redis=load_redis_config(config_dct["redis"]),
    )


def load_bot_config(dct: dict) -> BotConfig:
    return BotConfig(
        token=dct["token"],
        log_chat=dct["log_chat"],
        superusers=dct["superusers"],
        bot_api=load_botapi(dct["botapi"])
    )


def load_botapi(dct: dict) -> BotApiConfig:
    return BotApiConfig(
        type=BotApiType[dct["type"]],
        botapi_url=dct.get("botapi_url", None),
        botapi_file_url=dct.get("file_url", None),
    )