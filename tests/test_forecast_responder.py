import pytest
from unittest.mock import patch
from tests.mock_class.mock_bot_service import MockBotService
from tests.mock_data.mock_db_data import MOCK_WEATHER_FORECAST_DATA
from src.bot.forecast_responder import get_merged_forecasts
from src.models.domain_model import BotUserModel
from src.models.protocols import BotServiceProtocol
from src.exceptions import EmptyQueryResultError, NoForecastResultError


TEST_USER_MODEL = BotUserModel(chat_id=1, username=None, adm4_code="1234")


@pytest.fixture
def bot_service() -> BotServiceProtocol:
    return MockBotService()


async def test_get_merged_forecast_return_with_header_added(
    bot_service: BotServiceProtocol,
) -> None:
    result = await get_merged_forecasts(
        chat_id=1,
        user_data=TEST_USER_MODEL,
        get_forecast_service=bot_service.get_today_weather_forecast,
    )
    assert f"Forecast for {TEST_USER_MODEL.adm4_code}" in result
    assert "As of 15 August 2026" in result


async def test_get_merged_forecast_return_expected_total_forecasts(
    bot_service: BotServiceProtocol,
) -> None:
    """
    Test that get_merged_forecast() merge all given forecast in the iterable
    into a single str based on the given AsyncIterable total forecasts.
    """
    result = await get_merged_forecasts(
        chat_id=1,
        user_data=TEST_USER_MODEL,
        # get_today and get_tomorrow weather forecast
        # return the same AsyncIterable of the mocked data
        # see the implementation in: tests/mock_class/mock_bot_service.py
        get_forecast_service=bot_service.get_tomorrow_weather_forecast,
    )
    # test if the merged forecasts length match the actual
    # mocked data length
    assert result.count("Temp") == len(MOCK_WEATHER_FORECAST_DATA)


async def test_get_merged_forecast_raise_when_no_forecast_found(
    bot_service: BotServiceProtocol,
) -> None:
    fake_error = EmptyQueryResultError(
        {"start_dt": "2026-08-15 00:00:00", "end_dt": "2026-08-17 23:00:00"}
    )
    with patch.object(
        bot_service, "get_today_weather_forecast", side_effect=fake_error
    ):
        with pytest.raises(NoForecastResultError) as e:
            await get_merged_forecasts(
                chat_id=1,
                user_data=TEST_USER_MODEL,
                get_forecast_service=bot_service.get_today_weather_forecast,
            )
        assert e.value.chat_id == 1
        # "1234" is an adm4_code based on TEST_USER_MODEL
        assert "1234" in e.value.message
        assert fake_error.query["start_dt"] in e.value.message
        assert fake_error.query["end_dt"] in e.value.message
