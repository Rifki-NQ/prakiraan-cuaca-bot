import logging
import asyncio
from typing import TypeVar
from collections.abc import AsyncIterable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.models.dt_model import DatetimeModel
from src.models.domain_model import ForecastModel, BotUserModel, BotUserStateModel
from src.models.enums import UserLocationState
from src.models.protocols import (
    ETLQueryProtocol,
    BotQueryProtocol,
)
from src.exceptions import DependencyMissingError

logger = logging.getLogger(__name__)
T = TypeVar("T")
BOT_DATETIME = ZoneInfo("Asia/Jakarta")


class BotService:
    def __init__(
        self,
        etl_query: ETLQueryProtocol | None = None,
        bot_query: BotQueryProtocol | None = None,
    ) -> None:
        """Convert the dependency into each own dependency name when it's None."""
        self.etl_query = etl_query if etl_query else "ETLQuery"
        self.bot_query = bot_query if bot_query else "BotQuery"

    async def create_user(self, chat_id: int) -> None:
        bot_query = self._get_dependency_or_raise(
            self.bot_query, self.create_user.__qualname__
        )
        await bot_query.insert_or_update_user(BotUserModel(chat_id))
        logger.debug(f"user {chat_id} created")

    async def update_user(self, user: BotUserModel) -> None:
        bot_query = self._get_dependency_or_raise(
            self.bot_query, self.update_user.__qualname__
        )
        await bot_query.insert_or_update_user(user)
        logger.debug(f"user {user.chat_id} updated")

    async def check_user_location_state(self, chat_id: int) -> UserLocationState:
        bot_query = self._get_dependency_or_raise(
            self.bot_query, self.check_user_location_state.__qualname__
        )
        initial_user_state = await bot_query.get_user_state(chat_id)
        if initial_user_state is None:
            return UserLocationState.NO_STATE
        user_state = BotUserStateModel(**initial_user_state._mapping)  # pyright: ignore[reportPrivateUsage]
        if user_state.kabupaten_atau_kota is None:
            return UserLocationState.NO_CITY_OR_REGENCY
        elif user_state.kecamatan is None:
            return UserLocationState.NO_SUBDISTRICT
        elif user_state.desa_atau_kelurahan is None:
            return UserLocationState.NO_VILLAGE
        else:
            return UserLocationState.COMPLETE

    async def create_user_state(self, chat_id: int) -> None:
        bot_query = self._get_dependency_or_raise(
            self.bot_query, self.create_user_state.__qualname__
        )
        await bot_query.insert_or_update_user_state(BotUserStateModel(chat_id))
        logger.debug(f"user {chat_id} state created")

    async def update_user_state(self, user_state: BotUserStateModel) -> None:
        bot_query = self._get_dependency_or_raise(
            self.bot_query, self.update_user_state.__qualname__
        )
        await bot_query.insert_or_update_user_state(user_state)
        logger.debug(f"user {user_state.chat_id} state updated")

    def get_today_weather_forecast(
        self, adm4_code: str
    ) -> AsyncIterable[ForecastModel]:
        dt = self._setup_datetime()
        today_dt_range = (dt.current_datetime_start, dt.current_datetime_end)
        return self._yield_forecast(adm4_code, today_dt_range)

    def get_tomorrow_weather_forecast(
        self, adm4_code: str
    ) -> AsyncIterable[ForecastModel]:
        dt = self._setup_datetime(timedelta(days=1))
        tomorrow_dt_range = (dt.current_datetime_start, dt.current_datetime_end)
        return self._yield_forecast(adm4_code, tomorrow_dt_range)

    async def _yield_forecast(
        self, adm4_code: str, dt_range: tuple[datetime, datetime]
    ) -> AsyncIterable[ForecastModel]:
        etl_query = self._get_dependency_or_raise(
            self.etl_query, self._yield_forecast.__qualname__
        )
        rows = await etl_query.get_forecast_by_range(adm4_code, dt_range)
        async for row in rows:
            yield ForecastModel(**row._mapping)  # pyright: ignore[reportPrivateUsage]
            await asyncio.sleep(0)

    def _setup_datetime(self, timedelta: timedelta | None = None) -> DatetimeModel:
        """
        Return DatetimeModel with datetime.now(),
        add datetime.now() with timedelta if not None.
        """
        if timedelta is None:
            return DatetimeModel(datetime.now(tz=BOT_DATETIME))
        return DatetimeModel(datetime.now(tz=BOT_DATETIME) + timedelta)

    def _get_dependency_or_raise(self, dependency: T | str, method_name: str) -> T:
        """Used to get dependency for the method, raise error if the dependency is str."""
        if isinstance(
            dependency, str
        ):  # the str in dependency means it's missing the actual dependency
            raise DependencyMissingError(dependency, method_name)
        return dependency
