import asyncio
import logging
from typing import Any
from collections.abc import AsyncIterable, Iterable
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import csv
from sqlalchemy import (
    MetaData,
    Row,
    Table,
    Column,
    String,
    Integer,
    DateTime,
    Connection,
    select,
    between,
    create_engine,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine
from src.models.contexts import DBContext, LocalDBContext
from src.models.domain_model import UserDataModel, CSVLocationDataModel
from src.exceptions import (
    InvalidDatetimeRangeError,
    EmptyQueryResultError,
    DBNotInitializedError,
)


logger = logging.getLogger(__name__)


class BotQuery:
    BOT_TIMEZONE = ZoneInfo("Asia/Jakarta")

    def __init__(self) -> None:
        self._db: DBContext | None = None

    async def setup_db(self, db_url: str) -> None:
        """Must be called first before any other method."""
        engine = create_async_engine(db_url, pool_pre_ping=True)
        metadata = MetaData()
        offset_table = self._define_bot_offset_table(metadata)
        user_table = self._define_user_table(metadata)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.reflect)
            await conn.run_sync(metadata.create_all)
        self._db = DBContext(
            engine=engine,
            location_table=metadata.tables["forecast_location"],
            forecast_table=metadata.tables["weather_forecast"],
            offset_table=offset_table,
            user_table=user_table,
        )
        logger.debug("setup_db() executed")

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

    async def get_bot_offset(self, bot_token: str) -> Row[Any] | None:
        """Get or select bot_offset data if it exists."""
        db = self._get_db()
        async with db.engine.connect() as conn:
            stmt = select(db.offset_table).where(
                db.offset_table.c.bot_token == bot_token
            )
            result = await conn.execute(stmt)
            return result.fetchone()

    async def insert_or_update_bot_offset(
        self, bot_token: str, offset: int, update_time: datetime
    ) -> None:
        """Insert or update bot_offset data except the pk."""
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
                    if col.name not in pk_names
                },
            )
            await conn.execute(upsert_stmt)
        logger.debug("bot_offset commited to db")

    async def insert_or_update_user(self, user_data: UserDataModel) -> None:
        """
        Insert user data into the table or update if it conflicts,
        update all columns on conflict except the table pk and the 'created_at' column.
        """
        db = self._get_db()
        current_dt = self._get_current_datetime()
        pk_names = {pk.name for pk in db.user_table.primary_key.c}
        excluded_columns = {"created_at", *pk_names}

        async with db.engine.begin() as conn:
            stmt = insert(db.user_table).values(
                chat_id=user_data.chat_id,
                username=user_data.username,
                adm4_code=user_data.adm4_code,
                updated_at=current_dt,
                created_at=current_dt,
            )
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=list(pk_names),
                set_={
                    col.name: stmt.excluded[col.name]
                    for col in db.user_table.c
                    if col.name not in excluded_columns
                },
            ).returning(db.user_table.c.created_at)
            result = await conn.execute(upsert_stmt)
            row = result.fetchone()
            if row and row.created_at == current_dt:
                logger.debug(f"user {user_data.chat_id} inserted")
                return
            logger.debug(f"user {user_data.chat_id} updated")

    async def get_user(self, chat_id: int) -> Row[Any] | None:
        """Get or select user data if it exists."""
        db = self._get_db()
        async with db.engine.connect() as conn:
            stmt = select(db.user_table).where(db.user_table.c.chat_id == chat_id)
            result = await conn.execute(stmt)
            return result.fetchone()

    def _get_db(self) -> DBContext:
        """get the db attributes, can be called after setup_db()."""
        if self._db is None:
            raise DBNotInitializedError("setup_db() has not called yet")
        return self._db

    def _get_current_datetime(self) -> datetime:
        """Get current datetime with datetime.now() in Asia/Jakarta timezone,
        with the tzinfo removed."""
        current_datetime = datetime.now(tz=self.BOT_TIMEZONE)
        return current_datetime.replace(tzinfo=None)

    def _define_bot_offset_table(self, metadata: MetaData) -> Table:
        return Table(
            "bot_offset",
            metadata,
            Column("bot_token", String(), primary_key=True),
            Column("offset", Integer()),
            Column("updated_at", DateTime()),
        )

    def _define_user_table(self, metadata: MetaData) -> Table:
        return Table(
            "bot_user",
            metadata,
            Column("chat_id", Integer(), primary_key=True),
            Column("username", String(), nullable=True),
            Column("adm4_code", String()),
            Column("updated_at", DateTime()),
            Column("created_at", DateTime()),
        )


class LocationFinder:
    def __init__(self) -> None:
        self._local_db: LocalDBContext | None = None

    def setup_local_db(self, cwd_db_path: str) -> None:
        """Must be called once before any other method."""
        if self._local_db is not None:
            logger.warning("sqlite engine already created")
            return
        engine = create_engine(f"sqlite:///{cwd_db_path}")
        metadata = MetaData()
        location_table = self._define_location_table(metadata)
        with engine.connect() as conn:
            metadata.create_all(conn)
        self._local_db = LocalDBContext(engine=engine, location_table=location_table)
        logger.debug("setup_local_db() executed")

    def search_city_or_regency(self, city_or_regency: str) -> list[str] | None:
        """List all possible cities or regencies based of the given 'city_or_regency' value."""
        db = self._get_local_db()
        with db.engine.connect() as conn:
            stmt = (
                select(db.location_table.c.kabupaten_atau_kota)
                .distinct()
                .where(
                    db.location_table.c.kabupaten_atau_kota.like(f"%{city_or_regency}%")
                )
            )
            result = conn.execute(stmt).all()
            return [row.kabupaten_atau_kota for row in result] if result else None

    def search_subdistrict(self, city_or_regency: str) -> list[str] | None:
        """List all the subdistricts of the given city_or_regency name."""
        db = self._get_local_db()
        with db.engine.connect() as conn:
            stmt = (
                select(db.location_table.c.kecamatan)
                .distinct()
                .where(db.location_table.c.kabupaten_atau_kota == city_or_regency)
            )
            result = conn.execute(stmt).all()
            return [row.kecamatan for row in result] if result else None

    def search_village(
        self, city_or_regency: str, subdistrict: str
    ) -> list[str] | None:
        """List all the villages of the given city_or_regency and subdistrict name."""
        db = self._get_local_db()
        with db.engine.connect() as conn:
            stmt = (
                select(db.location_table.c.desa_atau_kelurahan)
                .distinct()
                .where(
                    (db.location_table.c.kabupaten_atau_kota == city_or_regency)
                    & (db.location_table.c.kecamatan == subdistrict)
                )
            )
            result = conn.execute(stmt).all()
            return [row.desa_atau_kelurahan for row in result] if result else None

    def start_csv_to_local_db_transformation(self, csv_filepath: Path) -> None:
        """
        Start the transformation from csv file to sqlite .db database,
        this method should only be called preferably once when the bot server started,
        since the process is slow and blocking.
        """
        db = self._get_local_db()
        logger.info("csv to local db transformation started")
        with db.engine.begin() as conn:
            for csv_row in self._get_rows_from_csv(csv_filepath):
                self._insert_or_ignore_location(conn, db.location_table, csv_row)
        logger.info("csv to local db transformation finished")

    def _insert_or_ignore_location(
        self, conn: Connection, table: Table, insert_value: CSVLocationDataModel
    ) -> None:
        """Insert or ignore the forecast_location table,
        using sqlite specific 'OR IGNORE' dialect to ignore the conflicting row."""
        stmt = insert(table).prefix_with("OR IGNORE").values(**insert_value.as_dict())
        result = conn.execute(stmt)
        if result.rowcount > 0:
            logger.debug(f"row {insert_value.kode_adm4} inserted")
            return
        logger.debug(f"row {insert_value.kode_adm4} ignored")

    def _get_rows_from_csv(self, csv_filepath: Path) -> Iterable[CSVLocationDataModel]:
        """
        Open the file then yield the converted csv row data into the domain model,
        with 'provinsi' column removed because it's not needed for the location lookup logic.
        """
        with open(csv_filepath, mode="r", newline="") as f:
            logger.debug(f"open file: {csv_filepath}")
            reader = csv.DictReader(f)
            for row in reader:
                row.pop("provinsi")  # delete not needed province column
                yield CSVLocationDataModel(**row)
        logger.debug(f"close file: {csv_filepath}")

    def _get_local_db(self) -> LocalDBContext:
        """Get the local db attribute, raise error if self._local_db is None or no setup yet."""
        if self._local_db is None:
            raise DBNotInitializedError("setup_local_db() has not called yet")
        return self._local_db

    def _define_location_table(self, metadata: MetaData) -> Table:
        return Table(
            "forecast_location",
            metadata,
            Column("kode_adm4", String(), primary_key=True),
            Column("kabupaten_atau_kota", String()),
            Column("kecamatan", String()),
            Column("desa_atau_kelurahan", String()),
        )
