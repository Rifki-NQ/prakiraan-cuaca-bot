import pytest
import pytest_asyncio
from unittest.mock import patch
from collections.abc import AsyncGenerator
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tests.tests_db import BotTestDB
from tests.mock_data.mock_db_data import (
    MOCK_BOT_OFFSET_DATA,
    MOCK_BOT_USER_DATA,
    MOCK_BOT_USER_STATE_DATA,
)
from tests.tests_utils import drop_all_tables, get_tables_name
from src.main import get_env
from src.queries.bot_query import BotQuery
from src.models.domain_model import BotUserModel, BotUserStateModel
from src.exceptions import DBNotInitializedError


pytestmark = pytest.mark.integration


load_dotenv()
bot_db_url = get_env("BOT_DATABASE_URL")
test_db_url = get_env("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def bot_engine() -> AsyncGenerator[AsyncEngine, None]:
    bot_engine = create_async_engine(bot_db_url)
    yield bot_engine
    await bot_engine.dispose()


@pytest_asyncio.fixture
async def bot_query(bot_engine: AsyncEngine) -> AsyncGenerator[BotQuery, None]:
    """
    Return an object of BotQuery, with the internal function:
    _get_db() patched with BotTestDB._get_db().

    The reason why BotQuery._get_db() gets patched is because
    BotTestDB uses it's own database, with the tables schema reflected from the production db
    and data seeded using predictable, mocked_data.
    """
    bot_query = BotQuery()
    test_db = BotTestDB()
    try:
        await test_db.setup_bot_test_db(test_db_url, bot_engine)
        await test_db.seed_bot_test_tables(
            mocked_bot_offset_data=MOCK_BOT_OFFSET_DATA,
            mocked_bot_user_data=MOCK_BOT_USER_DATA,
            mock_bot_user_state_data=MOCK_BOT_USER_STATE_DATA,
        )
        with patch.object(bot_query, "_get_db", return_value=test_db._get_db()):  # pyright: ignore[reportPrivateUsage]
            yield bot_query
    finally:
        # drop all tables then dispose the test_db engine
        test_db_engine = test_db._get_db().engine  # pyright: ignore[reportPrivateUsage]
        await drop_all_tables(test_db_engine)
        await test_db_engine.dispose()


@pytest_asyncio.fixture
async def prod_bot_query() -> AsyncGenerator[BotQuery, None]:
    """Return an object of BotQuery, connected with actual production database."""
    bot_query = BotQuery()
    # this method reflect then create the tables if not exists on the prod_db
    await bot_query.setup_bot_db(bot_db_url)
    db = bot_query._get_db()  # pyright: ignore[reportPrivateUsage]
    try:
        yield bot_query
    finally:
        # warning: do not drop the tables
        # since this is production database!
        await db.engine.dispose()


async def test_get_db_before_setup_bot_db() -> None:
    bot_query = BotQuery()
    with pytest.raises(DBNotInitializedError):
        bot_query._get_db()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.prod_db
def test_db_attributes_after_setup_bot_db(prod_bot_query: BotQuery) -> None:
    db = prod_bot_query._get_db()  # pyright: ignore[reportPrivateUsage]
    assert db is not None
    assert isinstance(db.engine, AsyncEngine)
    assert isinstance(db.bot_offset_table, Table)
    assert isinstance(db.bot_user_table, Table)
    assert isinstance(db.bot_user_state_table, Table)
    assert db.bot_offset_table.name == "bot_offset"
    assert db.bot_user_table.name == "bot_user"
    assert db.bot_user_state_table.name == "bot_user_state"
    
    
@pytest.mark.prod_db
async def test_setup_bot_db_create_tables_in_db(prod_bot_query: BotQuery) -> None:
    db = prod_bot_query._get_db()  # pyright: ignore[reportPrivateUsage]
    table_names_from_db = await get_tables_name(db.engine)
    assert db.bot_offset_table.name in table_names_from_db
    assert db.bot_user_table.name in table_names_from_db
    assert db.bot_user_state_table.name in table_names_from_db
    

async def test_get_bot_offset_return_expected(bot_query: BotQuery) -> None:
    result = await bot_query.get_bot_offset(MOCK_BOT_OFFSET_DATA["bot_token"])
    assert result is not None
    assert result.bot_token == MOCK_BOT_OFFSET_DATA["bot_token"]
    assert result.offset == MOCK_BOT_OFFSET_DATA["offset"]
    assert result.updated_at == MOCK_BOT_OFFSET_DATA["updated_at"]


async def test_get_user_return_expected(bot_query: BotQuery) -> None:
    result = await bot_query.get_user(MOCK_BOT_USER_DATA["chat_id"])
    assert result is not None
    assert result.chat_id == MOCK_BOT_USER_DATA["chat_id"]
    assert result.username is None
    assert result.adm4_code == MOCK_BOT_USER_DATA["adm4_code"]
    # deliberately not asserting updated_at and created_at column value
    # since the select statement excluded those columns


async def test_get_user_state_return_expected(bot_query: BotQuery) -> None:
    mock_data = MOCK_BOT_USER_STATE_DATA
    result = await bot_query.get_user_state(mock_data["chat_id"])
    assert result is not None
    assert result.chat_id == mock_data["chat_id"]
    assert result.kabupaten_atau_kota == mock_data["kabupaten_atau_kota"]
    assert result.kecamatan == mock_data["kecamatan"]
    assert result.desa_atau_kelurahan == mock_data["desa_atau_kelurahan"]
    # deliberately not asserting updated_at and created_at column value
    # since the select statement excluded those columns


async def test_get_methods_with_non_existent_params_in_db(bot_query: BotQuery) -> None:
    bot_offset_result = await bot_query.get_bot_offset("non_existent_bot_token")
    bot_user_result = await bot_query.get_user_state(-10)  # non existent chat_id
    bot_user_state_result = await bot_query.get_user_state(-10)  # non existent chat_id
    assert bot_offset_result is None
    assert bot_user_result is None
    assert bot_user_state_result is None


async def test_insert_or_update_bot_offset_without_conflict(
    bot_query: BotQuery, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test BotQuery.insert_or_update_bot_offset() with new data,
    which means there is no PK conflict with the upcoming new data.
    """
    caplog.set_level(10)  # DEBUG level
    await bot_query.insert_or_update_bot_offset(
        bot_token="new_fake_bot_token", offset=10, update_time=datetime(2026, 10, 10)
    )
    assert "bot_offset commited to db" in caplog.messages[0]
    result = await bot_query.get_bot_offset("new_fake_bot_token")
    assert result is not None
    assert result.bot_token == "new_fake_bot_token"
    assert result.offset == 10
    assert result.updated_at == datetime(2026, 10, 10)


async def test_insert_or_update_bot_offset_with_conflict(
    bot_query: BotQuery, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that insert stmt on the BotQuery.insert_or_update_bot_offset()
    with conflicting PK does not raise error but have the values updated instead.
    """
    caplog.set_level(10)  # DEBUG level
    await bot_query.insert_or_update_bot_offset(
        bot_token=MOCK_BOT_OFFSET_DATA[
            "bot_token"  # the conflicting PK
        ],
        offset=10,  # different value from seeded mocked_data
        update_time=datetime(2026, 10, 10),  # different value from seeded mocked_data
    )
    assert "bot_offset commited to db" in caplog.messages[0]
    result = await bot_query.get_bot_offset(MOCK_BOT_OFFSET_DATA["bot_token"])
    assert result is not None
    assert result.bot_token == MOCK_BOT_OFFSET_DATA["bot_token"]
    assert result.offset == 10
    assert result.updated_at == datetime(2026, 10, 10)


async def test_insert_or_updated_user_without_conflict(
    bot_query: BotQuery, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test BotQuery.insert_or_update_user() with new data,
    which means there is no PK conflict with the upcoming new data.
    """
    caplog.set_level(10)  # DEBUG level
    new_user = BotUserModel(chat_id=12345, username=None, adm4_code="32.16.20.2002")
    await bot_query.insert_or_update_user(new_user)
    assert "inserted" in caplog.messages[0]
    result = await bot_query.get_user(12345)
    assert result is not None
    assert result.chat_id == new_user.chat_id
    assert result.username == new_user.username
    assert result.adm4_code == new_user.adm4_code


async def test_insert_or_update_user_with_conflict(
    bot_query: BotQuery, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that insert stmt on BotQuery.insert_or_update_user()
    with conflicting PK does not raise an error, but instead,
    the values gets updated except the PK itself and the 'created_at' column.
    """
    caplog.set_level(10)  # DEBUG level
    conflicting_user = BotUserModel(
        chat_id=MOCK_BOT_USER_DATA["chat_id"],  # the conflicting PK
        username=None,
        adm4_code="32.16.20.2005",  # different value from seeded mocked_data
    )
    await bot_query.insert_or_update_user(conflicting_user)
    assert "updated" in caplog.messages[0]
    result = await bot_query.get_user(MOCK_BOT_USER_DATA["chat_id"])
    assert result is not None
    assert result.chat_id == conflicting_user.chat_id
    assert result.username == conflicting_user.username
    assert result.adm4_code == conflicting_user.adm4_code


async def test_insert_or_update_user_state_without_conflict(
    bot_query: BotQuery, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test BotQuery.insert_or_update_user_state() with new data,
    which means there is no PK conflict with the upcoming new data.
    """
    caplog.set_level(10)  # DEBUG level
    new_user_state = BotUserStateModel(
        chat_id=54321,
        kabupaten_atau_kota="location a",
        kecamatan="location b",
        desa_atau_kelurahan="location c",
    )
    await bot_query.insert_or_update_user_state(new_user_state)
    assert "inserted" in caplog.messages[0]
    result = await bot_query.get_user_state(new_user_state.chat_id)
    assert result is not None
    assert result.chat_id == new_user_state.chat_id
    assert result.kabupaten_atau_kota == new_user_state.kabupaten_atau_kota
    assert result.kecamatan == new_user_state.kecamatan
    assert result.desa_atau_kelurahan == new_user_state.desa_atau_kelurahan


async def test_insert_or_update_user_state_with_conflict(
    bot_query: BotQuery, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that insert stmt on BotQuery.insert_or_update_user_state()
    with conflicting PK does not raise an error, but instead,
    the values gets updated except the PK itself and the 'created_at' column.
    """
    caplog.set_level(10)  # DEBUG level
    mock_data = MOCK_BOT_USER_STATE_DATA
    conflicting_user_state = BotUserStateModel(
        chat_id=mock_data["chat_id"],  # the conflicting PK
        # different values from the seeded mocked_data
        kabupaten_atau_kota="diff location a",
        kecamatan="diff location b",
        desa_atau_kelurahan="diff location c",
    )
    await bot_query.insert_or_update_user_state(conflicting_user_state)
    assert "updated" in caplog.messages[0]
    result = await bot_query.get_user_state(mock_data["chat_id"])
    assert result is not None
    assert result.chat_id == conflicting_user_state.chat_id
    assert result.kabupaten_atau_kota == conflicting_user_state.kabupaten_atau_kota
    assert result.kecamatan == conflicting_user_state.kecamatan
    assert result.desa_atau_kelurahan == conflicting_user_state.desa_atau_kelurahan


def test_get_current_datetime_tz_removed() -> None:
    bot_query = BotQuery()
    current_dt = bot_query._get_current_datetime()  # pyright: ignore[reportPrivateUsage]
    assert current_dt.tzinfo is None


def test_exclude_timestamp_columns_removes_updated_and_created_at(
    bot_query: BotQuery,
) -> None:
    user_table = bot_query._get_db().bot_user_table  # pyright: ignore[reportPrivateUsage]
    should_excluded = {"updated_at", "created_at"}
    column_names = {
        c.name
        for c in bot_query._exclude_timestamp_columns(user_table)  # pyright: ignore[reportPrivateUsage]
    }
    assert column_names == {c.name for c in user_table.c} - should_excluded
    for name in should_excluded:
        assert name not in column_names
