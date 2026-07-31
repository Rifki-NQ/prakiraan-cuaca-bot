from typing import Protocol, Any
from collections.abc import AsyncIterable
from pathlib import Path
from datetime import datetime
from sqlalchemy import Row
from src.models.domain_model import ForecastModel, UserDataModel
from src.models.commands import Commands


class ETLQueryProtocol(Protocol):
    async def get_forecast_by_range(
        self, adm4_code: str, datetime_range: tuple[datetime, datetime]
    ) -> AsyncIterable[Row[Any]]: ...


class BotQueryProtocol(Protocol):
    async def get_bot_offset(self, bot_token: str) -> Row[Any] | None: ...
    async def insert_or_update_bot_offset(
        self, bot_token: str, offset: int, update_time: datetime
    ) -> None: ...
    async def get_user(self, chat_id: int) -> Row[Any] | None: ...
    async def insert_or_update_user(self, user_data: UserDataModel) -> None: ...


class LocationFinderProtocol(Protocol):
    async def search_city_or_regency(
        self, city_or_regency: str
    ) -> list[str] | None: ...
    async def search_subdistrict(self, city_or_regency: str) -> list[str] | None: ...
    async def search_village(
        self, city_or_regency: str, subdistrict: str
    ) -> list[str] | None: ...
    async def get_adm4_code(
        self, city_or_regency: str, subdistrict: str, village: str
    ) -> str | None: ...
    async def start_csv_to_local_db_transformation(
        self, csv_filepath: Path
    ) -> None: ...


class AppServiceProtocol(Protocol):
    def get_today_weather_forecast(self) -> AsyncIterable[ForecastModel]: ...
    def get_tomorrow_weather_forecast(self) -> AsyncIterable[ForecastModel]: ...


class CommandRouterProtocol(Protocol):
    def route_command(self, command: Commands) -> AsyncIterable[ForecastModel]: ...


class BotStateHandlerProtocol(Protocol):
    async def get_offset(self, bot_token: str) -> int | None: ...
    async def store_offset(self, bot_token: str, offset: int) -> None: ...
