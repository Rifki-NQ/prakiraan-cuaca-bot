import asyncio
from collections.abc import AsyncIterable
from datetime import datetime
from src.models.dt_model import DatetimeModel
from src.models.domain_model import ForecastModel
from src.models.protocols import QueryBuilderProtocol


class AppService:
    def __init__(self, query_builder: QueryBuilderProtocol) -> None:
        self.query = query_builder

    async def get_today_weather_forecast(self) -> AsyncIterable[ForecastModel]:
        dt = self._setup_datetime()
        today_dt_range = (dt.current_datetime_start, dt.current_datetime_end)
        rows = await self.query.get_forecast_by_range(today_dt_range)
        async for row in rows:
            yield ForecastModel(**row._mapping)  # pyright: ignore[reportPrivateUsage]
            await asyncio.sleep(0)

    def _setup_datetime(self) -> DatetimeModel:
        """Methods that need dt attribute need to get through here"""
        return DatetimeModel(datetime.now())
