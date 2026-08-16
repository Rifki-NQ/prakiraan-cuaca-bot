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
class BotTestDBContext:
    engine: AsyncEngine
    forecast_table: Table
    location_table: Table


class BotTestDB:
    def __init__(self) -> None:
        self._db: BotTestDBContext | None

    async def setup_test_db(self, test_db_url: str, etl_engine: AsyncEngine) -> None:
        engine = create_async_engine(test_db_url)
        metadata = MetaData()
        # copy the tables from the etl_engine/db
        # to the test db metadata
        async with etl_engine.connect() as conn:
            await conn.run_sync(metadata.reflect)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        self._db = BotTestDBContext(
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

    def _get_db(self) -> BotTestDBContext:
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
