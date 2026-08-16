import pytest
import pytest_asyncio
from unittest.mock import patch
from collections.abc import AsyncGenerator, AsyncIterable
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tests.tests_db import BotTestDB
from tests.tests_utils import drop_all_tables
from tests.mock_data.mock_db_data import (
    MOCK_WEATHER_FORECAST_DATA,
    MOCK_FORECAST_LOCATION_DATA,
    MOCK_ETL_DATA_INFO,
)
from src.main import get_env
from src.queries.etl_query import ETLQuery
from src.exceptions import (
    InvalidDatetimeRangeError,
    DBNotInitializedError,
    EmptyQueryResultError,
)


pytestmark = pytest.mark.integration


load_dotenv()
etl_db_url = get_env("ETL_DATABASE_URL")
test_db_url = get_env("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def etl_engine() -> AsyncGenerator[AsyncEngine, None]:
    etl_engine = create_async_engine(etl_db_url)
    yield etl_engine
    await etl_engine.dispose()


@pytest_asyncio.fixture
async def etl_query(etl_engine: AsyncEngine) -> AsyncGenerator[ETLQuery, None]:
    """
    Return an object of etl_query, with the internal function:
    _get_db() patched with test_db attributes.

    The reason why the database gets patched with it's own test database
    is because the test database is filled with predictable, mocked data.
    """
    etl_query = ETLQuery()
    test_db = BotTestDB()
    try:
        await test_db.setup_test_db(test_db_url, etl_engine)
        # seed/fill the test db with mocked data
        await test_db.seed_location_test_table(MOCK_FORECAST_LOCATION_DATA)
        await test_db.seed_forecast_test_table(MOCK_WEATHER_FORECAST_DATA)
        with patch.object(etl_query, "_get_db", return_value=test_db._get_db()):  # pyright: ignore[reportPrivateUsage]
            yield etl_query
    finally:
        # drop all tables then dispose the test_db engine
        test_db_engine = test_db._get_db().engine  # pyright: ignore[reportPrivateUsage]
        async with test_db_engine.begin() as conn:
            await drop_all_tables(conn)
        await test_db_engine.dispose()


@pytest.mark.parametrize(
    "start_dt", [datetime(2020, 2, 2, 1, 1, 1), datetime(2020, 2, 3)]
)
async def test_invalid_datetime_range(start_dt: datetime) -> None:
    """InvalidDatetimeRangeError should be raised when start_dt is greater than end_dt"""
    end_dt = datetime(2020, 2, 2)
    etl_query = ETLQuery()
    datetime_range = (start_dt, end_dt)
    with pytest.raises(InvalidDatetimeRangeError) as exc_info:
        await etl_query.get_forecast_by_range("", datetime_range)
    assert exc_info.value.start_dt == start_dt
    assert exc_info.value.end_dt == end_dt


def test_get_db_before_setup_etl_db() -> None:
    etl_query = ETLQuery()
    with pytest.raises(DBNotInitializedError):
        etl_query._get_db()  # pyright: ignore[reportPrivateUsage]


async def test_get_forecast_by_range_return_expected_type_and_total_rows(
    etl_query: ETLQuery,
) -> None:
    """
    Test that get_forecast_by_range() method return AsyncIterable,
    with total rows of 72, based on the given dt_range
    """
    mock_info = MOCK_ETL_DATA_INFO
    dt_range = (
        mock_info["oldest_forecast_datetime"],
        mock_info["newest_forecast_datetime"],
    )
    results = await etl_query.get_forecast_by_range(mock_info["adm4_code"], dt_range)
    assert isinstance(results, AsyncIterable)
    assert len([r async for r in results]) == 72


async def test_get_forecast_by_range_return_expected_first_row_values(
    etl_query: ETLQuery,
) -> None:
    mock_info = MOCK_ETL_DATA_INFO
    dt_range = (
        # only query the first row
        mock_info["oldest_forecast_datetime"],
        mock_info["oldest_forecast_datetime"],
    )
    results = await etl_query.get_forecast_by_range(mock_info["adm4_code"], dt_range)
    async for result in results:
        assert result.forecast_datetime == datetime(2026, 8, 15, 0, 0, 0)
        assert result.analysis_datetime == datetime(2026, 8, 14, 0, 0, 0)
        assert result.adm4_code == "32.16.21.2005"
        assert result.temperature == 26
        assert result.total_cloud_coverage == 6
        assert result.total_precipitation == 0
        assert result.weather_description == "Cerah"
        assert result.weather_description_eng == "Sunny"
        assert result.wind_direction_degree == 248
        assert result.wind_direction_compass == "SW"
        assert result.wind_direction_compass_to == "NE"
        assert result.wind_speed == 2
        assert result.humidity == 79
        assert result.visibility == 7997
        assert result.updated_at == datetime(2026, 8, 14, 14, 47, 13, 718599)
        assert result.created_at == datetime(2026, 8, 13, 5, 13, 15, 962720)


async def test_get_forecast_by_range_raise_empty_result(etl_query: ETLQuery) -> None:
    mock_info = MOCK_ETL_DATA_INFO
    dt_range = (
        # deliberately a range with no matching weather forecast,
        # i.e. no forecast_datetime falls between these two dates
        # in the mocked_data
        datetime(2026, 8, 10, 0, 0, 0),
        datetime(2026, 8, 11, 0, 0, 0),
    )
    # this does not raises EmptyQueryResultError
    # since this return only the AsyncIterable object
    results = await etl_query.get_forecast_by_range(mock_info["adm4_code"], dt_range)
    with pytest.raises(EmptyQueryResultError) as exc_info:
        # this raises because the AsyncIterable is iterated or consumed
        [r async for r in results]
    assert exc_info.value.query.get("adm4_code") == mock_info["adm4_code"]
    assert exc_info.value.query.get("start_dt") == dt_range[0].strftime(
        "%d-%m-%Y %H:%M:%S"
    )
    assert exc_info.value.query.get("end_dt") == dt_range[1].strftime(
        "%d-%m-%Y %H:%M:%S"
    )
