import asyncio
from typing import Any
from collections.abc import AsyncIterable
from datetime import datetime
from sqlalchemy import select, MetaData, between, Row
from sqlalchemy.ext.asyncio import AsyncEngine
from src.exceptions import InvalidDatetimeRangeError, EmptyQueryResultError


class QueryBuilder:
    def __init__(self, engine: AsyncEngine, metadata: MetaData) -> None:
        self.engine = engine
        self.metadata = metadata
        self.forecast_location = metadata.tables["forecast_location"]
        self.weather_forecast = metadata.tables["weather_forecast"]

    async def get_forecast_by_range(
        self, datetime_range: tuple[datetime, datetime]
    ) -> AsyncIterable[Row[Any]]:
        """Return Iterable of weather forecast rows if the range is valid"""
        start_dt, end_dt = datetime_range
        if start_dt > end_dt:
            raise InvalidDatetimeRangeError(start_dt, end_dt)

        async def _results() -> AsyncIterable[Row[Any]]:
            """
            Select then yield each single forecast lazily,
            while giving the event loop control with: await asyncio.sleep(0),
            raise error if total yielded is 0.
            """
            async with self.engine.connect() as conn:
                stmt = (
                    select(self.weather_forecast)
                    .where(
                        between(
                            self.weather_forecast.c.forecast_datetime, start_dt, end_dt
                        )
                    )
                    .order_by(self.weather_forecast.c.forecast_datetime)
                )
                result = await conn.stream(stmt, execution_options={"yield_per": 24})
                total_yielded = 0
                async for row in result:
                    yield row
                    await asyncio.sleep(0)
                    total_yielded += 1
                if total_yielded == 0:
                    raise EmptyQueryResultError("Error: query returned zero row")

        return _results()
