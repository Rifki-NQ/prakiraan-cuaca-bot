import pytest
from unittest.mock import AsyncMock, Mock
from collections.abc import AsyncIterable
from datetime import datetime, timedelta
from src.models.domain_model import (
    BotUserModel,
    BotUserStateModel,
    DatetimeModel,
    ForecastModel,
)
from src.models.contexts import BotUserStateContext
from src.models.enums import UserLocationState
from src.service import BotService
from tests.mock_class.mock_etl_query import MockETLQuery
from tests.mock_data.mock_row_data import (
    MOCK_BOT_QUERY_GET_USER_MAPPED,
    MOCK_BOT_QUERY_GET_USER_STATE_MAPPED,
)
from tests.mock_data.mock_db_data import MOCK_WEATHER_FORECAST_DATA


# this test module does not test BotService.create_or_update_user
# and BotService.create_or_update_user_state
# since they are just thin layers to call bot_query
# and contains no business logic in the BotService


@pytest.fixture
def bot_service() -> BotService:
    fake_user_row = Mock(_mapping=MOCK_BOT_QUERY_GET_USER_MAPPED)
    fake_user_state_row = Mock(_mapping=MOCK_BOT_QUERY_GET_USER_STATE_MAPPED)
    mock_bot_query = Mock()
    mock_bot_query.get_user = AsyncMock(return_value=fake_user_row)
    mock_bot_query.get_user_state = AsyncMock(return_value=fake_user_state_row)
    return BotService(MockETLQuery(), mock_bot_query)


@pytest.fixture
def bot_service_none_results() -> BotService:
    mock_bot_query = Mock()
    mock_bot_query.get_user = AsyncMock(return_value=None)
    mock_bot_query.get_user_state = AsyncMock(return_value=None)
    return BotService(MockETLQuery(), mock_bot_query)


async def test_get_user_return_expected(bot_service: BotService) -> None:
    result = await bot_service.get_user(123)
    assert isinstance(result, BotUserModel)
    assert result.chat_id == MOCK_BOT_QUERY_GET_USER_MAPPED.get("chat_id")
    assert result.username is None
    assert result.adm4_code == MOCK_BOT_QUERY_GET_USER_MAPPED.get("adm4_code")


async def test_get_user_state_return_expected(bot_service: BotService) -> None:
    result = await bot_service.get_user_state(123)
    assert isinstance(result, BotUserStateModel)
    assert result.chat_id == MOCK_BOT_QUERY_GET_USER_STATE_MAPPED.get("chat_id")
    assert result.kabupaten_atau_kota == MOCK_BOT_QUERY_GET_USER_STATE_MAPPED.get(
        "kabupaten_atau_kota"
    )
    assert result.kecamatan == MOCK_BOT_QUERY_GET_USER_STATE_MAPPED.get("kecamatan")
    assert result.desa_atau_kelurahan is None


async def test_resolve_user_location_state_return_expected(
    bot_service: BotService,
) -> None:
    result = await bot_service.resolve_user_location_state(123)
    assert isinstance(result, BotUserStateContext)
    assert isinstance(result.bot_user_state, BotUserStateModel)
    assert result.bot_user_state.chat_id == MOCK_BOT_QUERY_GET_USER_STATE_MAPPED.get(
        "chat_id"
    )
    assert (
        result.bot_user_state.kabupaten_atau_kota
        == MOCK_BOT_QUERY_GET_USER_STATE_MAPPED.get("kabupaten_atau_kota")
    )
    assert result.bot_user_state.kecamatan == MOCK_BOT_QUERY_GET_USER_STATE_MAPPED.get(
        "kecamatan"
    )
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert isinstance(result.user_location_state, UserLocationState)
    assert result.user_location_state == UserLocationState.NO_VILLAGE


async def test_get_user_return_none(bot_service_none_results: BotService) -> None:
    result = await bot_service_none_results.get_user(123)
    assert result is None


async def test_get_user_state_return_none(bot_service_none_results: BotService) -> None:
    result = await bot_service_none_results.get_user_state(123)
    assert result is None


async def test_resolve_user_location_state_when_user_has_no_state(
    bot_service_none_results: BotService,
) -> None:
    result = await bot_service_none_results.resolve_user_location_state(123)
    # still a BotUserStateContext object
    # even when the user has no user_state yet
    assert isinstance(result, BotUserStateContext)
    assert result.bot_user_state is None
    assert result.user_location_state == UserLocationState.NO_STATE


@pytest.mark.parametrize(
    "user_state, expected_result",
    [
        (BotUserStateModel(123), UserLocationState.NO_CITY_OR_REGENCY),
        (BotUserStateModel(123, "kabupaten bekasi"), UserLocationState.NO_SUBDISTRICT),
        (
            BotUserStateModel(123, "kabupaten bekasi", "cikarang selatan"),
            UserLocationState.NO_VILLAGE,
        ),
        (
            BotUserStateModel(123, "kabupaten bekasi", "serang baru", "sukasari"),
            UserLocationState.COMPLETE,
        ),
    ],
)
def test_derive_location_state_return_expected(
    user_state: BotUserStateModel,
    expected_result: UserLocationState,
    bot_service: BotService,
) -> None:
    """
    Test BotService._derive_location_state with different user_state
    that contains different None attributes.
    """
    result = bot_service._derive_location_state(user_state)  # pyright: ignore[reportPrivateUsage]
    assert result == expected_result


def test_setup_datetime_return_expected(bot_service: BotService) -> None:
    result = bot_service._setup_datetime()  # pyright: ignore[reportPrivateUsage]
    datetime_now = datetime.now()

    assert isinstance(result, DatetimeModel)
    # check whether DatetimeModel strip the tzinfo
    assert result.current_datetime.tzinfo is None
    assert result.current_datetime_start.tzinfo is None
    assert result.current_datetime_end.tzinfo is None

    assert result.current_datetime_start == datetime_now.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    assert result.current_datetime_end == datetime_now.replace(
        hour=23, minute=59, second=59, microsecond=0
    )


def test_setup_datetime_with_timedelta_return_expected(bot_service: BotService) -> None:
    """
    Test that the timedelta, which is 1 day for this test case
    is added to the returned DatetimeModel attributes.
    """
    result = bot_service._setup_datetime(timedelta(days=1))  # pyright: ignore[reportPrivateUsage]
    # also add 1 day to the datetime.now()
    datetime_now = datetime.now() + timedelta(days=1)
    assert result.current_datetime_start == datetime_now.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    assert result.current_datetime_end == datetime_now.replace(
        hour=23, minute=59, second=59, microsecond=0
    )


def test_get_today_and_get_tomorrow_forecast_return_async_iterable_type(
    bot_service: BotService,
) -> None:
    today_result = bot_service.get_today_weather_forecast("")
    tomorrow_result = bot_service.get_tomorrow_weather_forecast("")
    assert isinstance(today_result, AsyncIterable)
    assert isinstance(tomorrow_result, AsyncIterable)


async def test_get_today_and_get_tomorrow_return_forecast_model_iterable(
    bot_service: BotService,
) -> None:
    today_results = bot_service.get_today_weather_forecast("")
    tomorrow_results = bot_service.get_tomorrow_weather_forecast("")

    total_today_result = 0
    async for today_result in today_results:
        assert isinstance(today_result, ForecastModel)
        total_today_result += 1
    assert total_today_result == len(
        MOCK_WEATHER_FORECAST_DATA  # actual yielded mock data
    )

    total_tomorrow_result = 0
    async for tomorrow_result in tomorrow_results:
        assert isinstance(tomorrow_result, ForecastModel)
        total_tomorrow_result += 1
    assert total_tomorrow_result == len(
        MOCK_WEATHER_FORECAST_DATA  # actual yielded mock data
    )


async def test_get_today_weather_forecast_first_yielded(
    bot_service: BotService,
) -> None:
    results = bot_service.get_today_weather_forecast("")
    async for result in results:
        assert result.adm4_code == MOCK_WEATHER_FORECAST_DATA[0].get("adm4_code")
        assert result.forecast_datetime == MOCK_WEATHER_FORECAST_DATA[0].get(
            "forecast_datetime"
        )
        assert result.analysis_datetime == MOCK_WEATHER_FORECAST_DATA[0].get(
            "analysis_datetime"
        )
        assert result.temperature == MOCK_WEATHER_FORECAST_DATA[0].get("temperature")
        assert result.total_cloud_coverage == MOCK_WEATHER_FORECAST_DATA[0].get(
            "total_cloud_coverage"
        )
        assert result.weather_description == MOCK_WEATHER_FORECAST_DATA[0].get(
            "weather_description"
        )
        assert result.weather_description_eng == MOCK_WEATHER_FORECAST_DATA[0].get(
            "weather_description_eng"
        )
        assert result.wind_direction_degree == MOCK_WEATHER_FORECAST_DATA[0].get(
            "wind_direction_degree"
        )
        assert result.wind_direction_compass == MOCK_WEATHER_FORECAST_DATA[0].get(
            "wind_direction_compass"
        )
        assert result.wind_direction_compass_to == MOCK_WEATHER_FORECAST_DATA[0].get(
            "wind_direction_compass_to"
        )
        assert result.wind_speed == MOCK_WEATHER_FORECAST_DATA[0].get("wind_speed")
        assert result.humidity == MOCK_WEATHER_FORECAST_DATA[0].get("humidity")
        assert result.visibility == MOCK_WEATHER_FORECAST_DATA[0].get("visibility")
        assert result.updated_at == MOCK_WEATHER_FORECAST_DATA[0].get("updated_at")
        assert result.created_at == MOCK_WEATHER_FORECAST_DATA[0].get("created_at")
        break  # test only the first yielded value


async def test_get_tomorrow_weather_forecast_first_yielded(
    bot_service: BotService,
) -> None:
    results = bot_service.get_tomorrow_weather_forecast("")
    async for result in results:
        assert result.adm4_code == MOCK_WEATHER_FORECAST_DATA[0].get("adm4_code")
        assert result.forecast_datetime == MOCK_WEATHER_FORECAST_DATA[0].get(
            "forecast_datetime"
        )
        assert result.analysis_datetime == MOCK_WEATHER_FORECAST_DATA[0].get(
            "analysis_datetime"
        )
        assert result.temperature == MOCK_WEATHER_FORECAST_DATA[0].get("temperature")
        assert result.total_cloud_coverage == MOCK_WEATHER_FORECAST_DATA[0].get(
            "total_cloud_coverage"
        )
        assert result.weather_description == MOCK_WEATHER_FORECAST_DATA[0].get(
            "weather_description"
        )
        assert result.weather_description_eng == MOCK_WEATHER_FORECAST_DATA[0].get(
            "weather_description_eng"
        )
        assert result.wind_direction_degree == MOCK_WEATHER_FORECAST_DATA[0].get(
            "wind_direction_degree"
        )
        assert result.wind_direction_compass == MOCK_WEATHER_FORECAST_DATA[0].get(
            "wind_direction_compass"
        )
        assert result.wind_direction_compass_to == MOCK_WEATHER_FORECAST_DATA[0].get(
            "wind_direction_compass_to"
        )
        assert result.wind_speed == MOCK_WEATHER_FORECAST_DATA[0].get("wind_speed")
        assert result.humidity == MOCK_WEATHER_FORECAST_DATA[0].get("humidity")
        assert result.visibility == MOCK_WEATHER_FORECAST_DATA[0].get("visibility")
        assert result.updated_at == MOCK_WEATHER_FORECAST_DATA[0].get("updated_at")
        assert result.created_at == MOCK_WEATHER_FORECAST_DATA[0].get("created_at")
        break  # test only the first yielded value
