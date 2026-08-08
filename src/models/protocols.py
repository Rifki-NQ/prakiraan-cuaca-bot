from typing import Protocol, Any
from collections.abc import AsyncIterable
from pathlib import Path
from datetime import datetime
from sqlalchemy import Row
from src.models.domain_model import (
    ForecastModel,
    BotUserModel,
    BotUserStateModel,
    LocationFlowResult,
    LocationFlowResultComplete,
)
from src.models.enums import Commands
from src.models.contexts import BotUserStateContext


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
    async def insert_or_update_user(self, user_data: BotUserModel) -> None: ...
    async def get_user_state(self, chat_id: int) -> Row[Any] | None: ...
    async def insert_or_update_user_state(
        self, user_state_data: BotUserStateModel
    ) -> None: ...


class LocationFinderProtocol(Protocol):
    async def search_city_or_regency(self, city_or_regency: str) -> list[str]: ...
    async def search_subdistrict(self, city_or_regency: str) -> list[str]: ...
    async def search_village(
        self, city_or_regency: str, subdistrict: str
    ) -> list[str]: ...
    async def get_adm4_code(
        self, city_or_regency: str, subdistrict: str, village: str
    ) -> str: ...
    async def start_csv_to_local_db_transformation(
        self, csv_filepath: Path
    ) -> None: ...


class LocationFlowHandlerProtocol(Protocol):
    async def handle_input_for_city_or_regency(
        self, chat_id: int, city_or_regency: str | None
    ) -> LocationFlowResult: ...
    async def handle_input_for_subdistrict(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        subdistrict: str | None,
    ) -> LocationFlowResult: ...
    async def handle_input_for_village(
        self, chat_id: int, user_state: BotUserStateModel | None, village: str | None
    ) -> LocationFlowResult | LocationFlowResultComplete: ...


class BotServiceProtocol(Protocol):
    async def create_or_update_user(self, user: BotUserModel) -> None: ...
    async def get_user(self, chat_id: int) -> BotUserModel | None: ...
    async def resolve_user_location_state(
        self, chat_id: int
    ) -> BotUserStateContext: ...
    async def create_or_update_user_state(
        self, user_state: BotUserStateModel
    ) -> None: ...
    async def get_user_state(self, chat_id: int) -> BotUserStateModel | None: ...
    def get_today_weather_forecast(
        self, adm4_code: str
    ) -> AsyncIterable[ForecastModel]: ...
    def get_tomorrow_weather_forecast(
        self, adm4_code: str
    ) -> AsyncIterable[ForecastModel]: ...


class BotStateHandlerProtocol(Protocol):
    async def get_offset(self, bot_token: str) -> int | None: ...
    async def store_offset(self, bot_token: str, offset: int) -> None: ...


class BotRespondHandlerProtocol(Protocol):
    async def parse_command(
        self, chat_id: int, command: Commands, input_value: str | None = None
    ) -> str: ...
