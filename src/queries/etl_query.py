import asyncio
import logging
from collections.abc import AsyncIterable
from datetime import datetime
from types import TracebackType
from typing import Any, Self

from sqlalchemy import (
    MetaData,
    Row,
    between,
    select,
)
from sqlalchemy.ext.asyncio import create_async_engine

from src.exceptions import (
    DBNotInitializedError,
    EmptyQueryResultError,
    InvalidDatetimeRangeError,
)
from src.models.contexts import ETLDBContext

logger = logging.getLogger(__name__)


class ETLQuery:
    RESULT_YIELD_PER_VALUE = 24  # server-side rows-per-yield streaming value

    def __init__(self, etl_db_url: str) -> None:
        self.etl_db_url = etl_db_url
        self._etl_db: ETLDBContext | None = None

    async def _setup_etl_db(self) -> None:
        """Should only be called in __aenter__() (as async context manager)"""
        if self._etl_db is not None:
            logger.warning("setup_etl_db() is already called")
            return
        engine = create_async_engine(self.etl_db_url, pool_pre_ping=True)
        try:
            metadata = MetaData()
            async with engine.begin() as conn:
                await conn.run_sync(metadata.reflect)
                await conn.run_sync(metadata.create_all)
        except BaseException:
            await engine.dispose()
            raise
        self._etl_db = ETLDBContext(
            engine=engine,
            location_table=metadata.tables["forecast_location"],
            forecast_table=metadata.tables["weather_forecast"],
        )
        logger.debug("setup_etl_db() executed")

    async def _close_etl_db(self) -> None:
        """Should only be called in __aexit__() (as async context manager)"""
        if self._etl_db is None:
            logger.warning("etl db is already closed")
            return
        try:
            await self._get_etl_db().engine.dispose()
        finally:
            self._etl_db = None
            logger.debug("etl db closed")

    async def __aenter__(self) -> Self:
        await self._setup_etl_db()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._close_etl_db()

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
            db = self._get_etl_db()
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
                result = await conn.stream(
                    stmt, execution_options={"yield_per": self.RESULT_YIELD_PER_VALUE}
                )
                total_yielded = 0
                async for row in result:
                    yield row
                    logger.debug(f"yielded forecast date: {row.forecast_datetime}")
                    await asyncio.sleep(0)
                    total_yielded += 1
                if total_yielded == 0:
                    raise EmptyQueryResultError(
                        {
                            "adm4_code": adm4_code,
                            "start_dt": start_dt.strftime("%d-%m-%Y %H:%M:%S"),
                            "end_dt": end_dt.strftime("%d-%m-%Y %H:%M:%S"),
                        }
                    )

        return _results()

    def _get_etl_db(self) -> ETLDBContext:
        """get the db attributes, can be called after setup_etl_db()."""
        if self._etl_db is None:
            raise DBNotInitializedError("setup_etl_db() has not called yet")
        return self._etl_db
