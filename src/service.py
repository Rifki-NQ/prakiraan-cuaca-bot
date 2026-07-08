import asyncio
from collections.abc import AsyncIterable
from datetime import datetime, timedelta
from src.models.dt_model import DatetimeModel
from src.models.domain_model import ForecastModel
from src.models.protocols import QueryBuilderProtocol


class AppService:
    def __init__(self, query_builder: QueryBuilderProtocol) -> None:
        self.query = query_builder

    def get_today_weather_forecast(self) -> AsyncIterable[ForecastModel]:
        dt = self._setup_datetime()
        today_dt_range = (dt.current_datetime_start, dt.current_datetime_end)
        return self._yield_forecast(today_dt_range)

    def get_tomorrow_weather_forecast(self) -> AsyncIterable[ForecastModel]:
        dt = self._setup_datetime(timedelta(days=1))
        tomorrow_dt_range = (dt.current_datetime_start, dt.current_datetime_end)
        return self._yield_forecast(tomorrow_dt_range)

    async def _yield_forecast(
        self, dt_range: tuple[datetime, datetime]
    ) -> AsyncIterable[ForecastModel]:
        rows = await self.query.get_forecast_by_range(dt_range)
        async for row in rows:
            yield ForecastModel(**row._mapping)  # pyright: ignore[reportPrivateUsage]
            await asyncio.sleep(0)

    def _setup_datetime(self, timedelta: timedelta | None = None) -> DatetimeModel:
        """
        Return DatetimeModel with datetime.now(),
        add datetime.now() with timedelta if not None.
        """
        if timedelta is None:
            return DatetimeModel(datetime.now())
        return DatetimeModel(datetime.now() + timedelta)
