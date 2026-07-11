import asyncio
import logging
from typing import Any
from collections.abc import AsyncIterable
from datetime import datetime
from sqlalchemy import (
    MetaData,
    Row,
    Table,
    Column,
    String,
    Integer,
    DateTime,
    select,
    between,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine
from src.models.contexts import DBContext
from src.exceptions import (
    InvalidDatetimeRangeError,
    EmptyQueryResultError,
    DBNotInitializedError,
)


logger = logging.getLogger(__name__)


class QueryBuilder:
    def __init__(self) -> None:
        self._db: DBContext | None = None

    async def setup_db(self, db_url: str) -> None:
        """Must be called first before any other method."""
        engine = create_async_engine(db_url, pool_pre_ping=True)
        metadata = MetaData()
        offset_table = self._define_bot_offset_table(metadata)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.reflect)
            await conn.run_sync(metadata.create_all)
        self._db = DBContext(
            engine=engine,
            location_table=metadata.tables["forecast_location"],
            forecast_table=metadata.tables["weather_forecast"],
            offset_table=offset_table,
        )
        logger.debug("setup_db() executed")

    async def get_forecast_by_range(
        self, datetime_range: tuple[datetime, datetime]
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
                        between(db.forecast_table.c.forecast_datetime, start_dt, end_dt)
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

    async def get_bot_offset(self, bot_token: str) -> Row[Any] | None:
        db = self._get_db()
        async with db.engine.connect() as conn:
            stmt = select(db.offset_table).where(
                db.offset_table.c.bot_token == bot_token
            )
            result = await conn.execute(stmt)
            return result.fetchone()

    async def store_bot_offset(
        self, bot_token: str, offset: int, update_time: datetime
    ) -> None:
        db = self._get_db()
        async with db.engine.begin() as conn:
            stmt = insert(db.offset_table).values(
                bot_token=bot_token, offset=offset, updated_at=update_time
            )
            pk_names = {pk.name for pk in db.offset_table.primary_key.c}
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=pk_names,
                set_={
                    col.name: stmt.excluded[col.name]
                    for col in db.offset_table.c
                    if col not in pk_names
                },
            )
            await conn.execute(upsert_stmt)
        logger.debug("bot_offset commited to db")

    def _get_db(self) -> DBContext:
        """Can be called after setup_db()."""
        if self._db is None:
            raise DBNotInitializedError("setup_db() has not called yet")
        return self._db

    def _define_bot_offset_table(self, metadata: MetaData) -> Table:
        return Table(
            "bot_offset",
            metadata,
            Column("bot_token", String(), primary_key=True),
            Column("offset", Integer()),
            Column("updated_at", DateTime()),
        )
