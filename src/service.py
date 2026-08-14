import logging
import asyncio
from collections.abc import AsyncIterable
from datetime import datetime, timedelta
from src.models.dt_model import DatetimeModel
from src.models.domain_model import ForecastModel, BotUserModel, BotUserStateModel
from src.models.enums import UserLocationState
from src.models.contexts import BotUserStateContext
from src.models.protocols import (
    ETLQueryProtocol,
    BotQueryProtocol,
)
from src.utils import BOT_DATETIME

logger = logging.getLogger(__name__)


class BotService:
    def __init__(
        self,
        etl_query: ETLQueryProtocol,
        bot_query: BotQueryProtocol,
    ) -> None:
        self.etl_query = etl_query
        self.bot_query = bot_query

    async def create_or_update_user(self, user: BotUserModel) -> None:
        await self.bot_query.insert_or_update_user(user)

    async def get_user(self, chat_id: int) -> BotUserModel | None:
        query_result = await self.bot_query.get_user(chat_id)
        if query_result is None:
            return None
        return BotUserModel(**query_result._mapping)  # pyright: ignore[reportPrivateUsage]

    async def resolve_user_location_state(self, chat_id: int) -> BotUserStateContext:
        initial_user_state = await self.bot_query.get_user_state(chat_id)
        if initial_user_state is None:
            return BotUserStateContext(
                user_location_state=UserLocationState.NO_STATE, bot_user_state=None
            )
        user_state = BotUserStateModel(**initial_user_state._mapping)  # pyright: ignore[reportPrivateUsage]
        return BotUserStateContext(
            user_location_state=self._derive_location_state(user_state),
            bot_user_state=user_state,
        )

    async def create_or_update_user_state(self, user_state: BotUserStateModel) -> None:
        await self.bot_query.insert_or_update_user_state(user_state)

    async def get_user_state(self, chat_id: int) -> BotUserStateModel | None:
        query_result = await self.bot_query.get_user_state(chat_id)
        if query_result is None:
            return None
        return BotUserStateModel(**query_result._mapping)  # pyright: ignore[reportPrivateUsage]

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
        rows = await self.etl_query.get_forecast_by_range(adm4_code, dt_range)
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

    def _derive_location_state(
        self, user_state: BotUserStateModel
    ) -> UserLocationState:
        if user_state.kabupaten_atau_kota is None:
            return UserLocationState.NO_CITY_OR_REGENCY
        elif user_state.kecamatan is None:
            return UserLocationState.NO_SUBDISTRICT
        elif user_state.desa_atau_kelurahan is None:
            return UserLocationState.NO_VILLAGE
        else:
            return UserLocationState.COMPLETE
