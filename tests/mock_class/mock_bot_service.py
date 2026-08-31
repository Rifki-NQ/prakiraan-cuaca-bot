import asyncio
from typing import Any
from collections.abc import AsyncIterable
from datetime import datetime
from tests.mock_data.mock_db_data import MOCK_WEATHER_FORECAST_DATA
from src.models.contexts import BotUserStateContext
from src.models.domain_model import ForecastModel, BotUserModel, BotUserStateModel


class MockBotService:
    # TODO: return mocked data for all methods

    async def create_or_update_user(self, user: BotUserModel) -> None:
        pass

    async def get_user(self, chat_id: int) -> BotUserModel | None:
        pass

    async def resolve_user_location_state(self, chat_id: int) -> BotUserStateContext:  # type: ignore
        pass

    async def create_or_update_user_state(self, user_state: BotUserStateModel) -> None:
        pass

    async def get_user_state(self, chat_id: int) -> BotUserStateModel | None:
        pass

    def get_today_weather_forecast(
        self, adm4_code: str
    ) -> AsyncIterable[ForecastModel]:
        return self._yield_forecast(MOCK_WEATHER_FORECAST_DATA)

    def get_tomorrow_weather_forecast(
        self, adm4_code: str
    ) -> AsyncIterable[ForecastModel]:
        return self._yield_forecast(MOCK_WEATHER_FORECAST_DATA)

    async def _yield_forecast(
        self, mock_data: list[dict[str, Any]]
    ) -> AsyncIterable[ForecastModel]:
        for single_data in mock_data:
            item = self._format_timestamps(single_data.copy())
            yield ForecastModel(**item)
            await asyncio.sleep(0)

    def _format_timestamps(self, single_data: dict[str, Any]) -> dict[str, Any]:
        single_data["forecast_datetime"] = datetime.strptime(
            single_data["forecast_datetime"], "%Y-%m-%d %H:%M:%S"
        )
        single_data["analysis_datetime"] = datetime.strptime(
            single_data["analysis_datetime"], "%Y-%m-%d %H:%M:%S"
        )
        return single_data
