from typing import Protocol, Any
from collections.abc import AsyncIterable
from datetime import datetime
from sqlalchemy import Row
from src.models.domain_model import ForecastModel
from src.models.commands import Commands


class QueryBuilderProtocol(Protocol):
    async def get_forecast_by_range(
        self, datetime_range: tuple[datetime, datetime]
    ) -> AsyncIterable[Row[Any]]: ...

    async def get_bot_offset(self, bot_token: str) -> Row[Any] | None: ...
    async def store_bot_offset(
        self, bot_token: str, offset: int, update_time: datetime
    ) -> None: ...


class AppServiceProtocol(Protocol):
    def get_today_weather_forecast(self) -> AsyncIterable[ForecastModel]: ...
    def get_tomorrow_weather_forecast(self) -> AsyncIterable[ForecastModel]: ...


class CommandRouterProtocol(Protocol):
    def route_command(self, command: Commands) -> AsyncIterable[ForecastModel]: ...


class BotStateHandlerProtocol(Protocol):
    async def get_offset(self, bot_token: str) -> int | None: ...
    async def store_offset(self, bot_token: str, offset: int) -> None: ...
