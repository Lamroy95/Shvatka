import pytest

from infrastructure.db.dao.holder import HolderDao
from tests.fixtures.user_constants import create_tg_user, create_dto_harry, OLD_HARRY_USERNAME
from tests.utils.user import assert_user
from tgbot.middlewares.data_load_middleware import save_user


@pytest.mark.asyncio
async def test_save_user(dao: HolderDao):
    data = dict(event_from_user=create_tg_user())
    actual = await save_user(data, dao)
    expected = create_dto_harry()
    assert_user(expected, actual)
    assert actual.db_id is not None
    assert await dao.user.count() == 1


@pytest.mark.asyncio
async def test_upsert_user(dao: HolderDao):
    old_tg_user = create_tg_user(username=OLD_HARRY_USERNAME)
    data = dict(event_from_user=old_tg_user)
    old = await save_user(data, dao)
    expected_old = create_dto_harry()
    expected_old.username = OLD_HARRY_USERNAME
    assert_user(expected_old, old)

    data = dict(event_from_user=create_tg_user())
    actual = await save_user(data, dao)

    expected = create_dto_harry()
    assert_user(expected, actual)
    assert old.db_id == actual.db_id
    assert await dao.user.count() == 1
