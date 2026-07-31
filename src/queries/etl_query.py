import asyncio
import logging
from typing import Any
from collections.abc import AsyncIterable
from datetime import datetime
from sqlalchemy import (
    MetaData,
    Row,
    select,
    between,
)
from sqlalchemy.ext.asyncio import create_async_engine
from src.models.contexts import ETLDBContext
from src.exceptions import (
    InvalidDatetimeRangeError,
    EmptyQueryResultError,
    DBNotInitializedError,
)


logger = logging.getLogger(__name__)


class ETLQuery:
    def __init__(self) -> None:
        self._db: ETLDBContext | None = None

    async def setup_etl_db(self, db_url: str) -> None:
        """Must be called first before any other method."""
        engine = create_async_engine(db_url, pool_pre_ping=True)
        metadata = MetaData()
        async with engine.begin() as conn:
            await conn.run_sync(metadata.reflect)
            await conn.run_sync(metadata.create_all)
        self._db = ETLDBContext(
            engine=engine,
            location_table=metadata.tables["forecast_location"],
            forecast_table=metadata.tables["weather_forecast"],
        )
        logger.debug("setup_etl_db() executed")

    async def get_forecast_by_range(
        self, adm4_code: str, datetime_range: tuple[datetime, datetime]
    ) -> AsyncIterable[Row[Any]]:
        """Return Iterable of weather forecast rows if the range is valid."""
        start_dt, end_dt = datetime_range
        if start_dt > end_dt:
            raise InvalidDatetimeRangeError(start_dt, end_dt)

        async def _results() -> AsyncIterable[Row[Any]]:
            """
            Select then yield each single forecast lazily,
            while giving the event loop control with: await asyncio.sleep(0),
            raise error if total yielded is 0.
            """
            db = self._get_db()
            async with db.engine.connect() as conn:
                stmt = (
                    select(db.forecast_table)
                    .where(
                        db.forecast_table.c.adm4_code == adm4_code,
                        between(
                            db.forecast_table.c.forecast_datetime, start_dt, end_dt
                        ),
                    )
                    .order_by(db.forecast_table.c.forecast_datetime)
                )
                result = await conn.stream(stmt, execution_options={"yield_per": 24})
                total_yielded = 0
                async for row in result:
                    yield row
                    logger.debug(f"yielded forecast date: {row.forecast_datetime}")
                    await asyncio.sleep(0)
                    total_yielded += 1
                if total_yielded == 0:
                    raise EmptyQueryResultError("Error: query returned zero row")

        return _results()

    def _get_db(self) -> ETLDBContext:
        """get the db attributes, can be called after setup_etl_db()."""
        if self._db is None:
            raise DBNotInitializedError("setup_db() has not called yet")
        return self._db
