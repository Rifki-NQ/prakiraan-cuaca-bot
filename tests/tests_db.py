"""This module has the responsibility to setup and seed the testing database."""

import logging
from typing import Any
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy import Table, MetaData
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from src.exceptions import DBNotInitializedError


logger = logging.getLogger(__name__)


@dataclass
class ETLTestDBContext:
    engine: AsyncEngine
    forecast_table: Table
    location_table: Table


@dataclass
class BotTestDBContext:
    engine: AsyncEngine
    bot_offset_table: Table
    bot_user_table: Table
    bot_user_state_table: Table


class ETLTestDB:
    def __init__(self) -> None:
        self._db: ETLTestDBContext | None

    async def setup_etl_test_db(
        self, test_db_url: str, etl_engine: AsyncEngine
    ) -> None:
        engine = create_async_engine(test_db_url)
        metadata = MetaData()
        # copy the tables schema from the etl_engine
        # to the test db metadata
        async with etl_engine.connect() as conn:
            await conn.run_sync(metadata.reflect)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        self._db = ETLTestDBContext(
            engine=engine,
            forecast_table=metadata.tables["weather_forecast"],
            location_table=metadata.tables["forecast_location"],
        )
        logger.info("setup_test_db() executed")

    async def seed_forecast_test_table(self, mocked_data: list[dict[str, Any]]) -> None:
        """Insert the weather_forecast table with mocked data."""
        db = self._get_db()
        async with db.engine.begin() as conn:
            stmt = insert(db.forecast_table).on_conflict_do_nothing()
            await conn.execute(stmt, self._normalize_forecast_mock_data(mocked_data))
        logger.debug("mocked_data for forecast_table inserted")

    async def seed_location_test_table(self, mocked_data: dict[str, Any]) -> None:
        db = self._get_db()
        async with db.engine.begin() as conn:
            stmt = (
                insert(db.location_table).on_conflict_do_nothing().values(mocked_data)
            )
            await conn.execute(stmt)
        logger.debug("mocked_data for location_table inserted")

    def _get_db(self) -> ETLTestDBContext:
        if self._db is None:
            raise DBNotInitializedError("setup_test_db() has not called yet")
        return self._db

    def _normalize_forecast_mock_data(
        self, mocked_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for single_mock_data in mocked_data:
            # copy the single_mock_data as 'item'
            # with the purpose of not mutating the original mock data
            item = single_mock_data.copy()
            item["forecast_datetime"] = datetime.strptime(
                item["forecast_datetime"], "%Y-%m-%d %H:%M:%S"
            )
            item["analysis_datetime"] = datetime.strptime(
                item["analysis_datetime"], "%Y-%m-%d %H:%M:%S"
            )
            item["updated_at"] = datetime.strptime(
                item["updated_at"], "%Y-%m-%d %H:%M:%S.%f"
            )
            item["created_at"] = datetime.strptime(
                item["created_at"], "%Y-%m-%d %H:%M:%S.%f"
            )
            normalized.append(item)
        return normalized


class BotTestDB:
    def __init__(self) -> None:
        self._db: BotTestDBContext | None

    async def setup_bot_test_db(
        self, test_db_url: str, bot_engine: AsyncEngine
    ) -> None:
        engine = create_async_engine(test_db_url)
        metadata = MetaData()
        # copy the tables schema from bot_engine
        # to the test db metadata
        async with bot_engine.connect() as conn:
            await conn.run_sync(metadata.reflect)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        self._db = BotTestDBContext(
            engine=engine,
            bot_offset_table=metadata.tables["bot_offset"],
            bot_user_table=metadata.tables["bot_user"],
            bot_user_state_table=metadata.tables["bot_user_state"],
        )

    async def seed_bot_test_tables(
        self,
        mocked_bot_offset_data: dict[str, Any],
        mocked_bot_user_data: dict[str, Any],
        mock_bot_user_state_data: dict[str, Any],
    ) -> None:
        db = self._get_db()
        table_and_mock_data = {
            db.bot_offset_table: mocked_bot_offset_data,
            db.bot_user_table: mocked_bot_user_data,
            db.bot_user_state_table: mock_bot_user_state_data,
        }
        async with db.engine.begin() as conn:
            for table, mock_data in table_and_mock_data.items():
                stmt = insert(table).on_conflict_do_nothing().values(mock_data)
                await conn.execute(stmt)
        logger.info("mocked_data for bot test tables inserted")

    def _get_db(self) -> BotTestDBContext:
        if self._db is None:
            raise DBNotInitializedError("setup_test_db() has not called yet")
        return self._db
