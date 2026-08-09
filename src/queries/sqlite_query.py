import logging
import csv
from typing import cast, Any
from collections.abc import Iterable
from pathlib import Path
from sqlalchemy import MetaData, Table, Column, String, Row, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from src.models.contexts import LocalDBContext
from src.models.domain_model import CSVLocationDataModel
from src.exceptions import DBNotInitializedError, EmptyQueryResultError

logger = logging.getLogger(__name__)


class LocationFinder:
    """
    Group of methods to find adm4_code through a series of
    location finding, from city_or_regency, to subdistrict and lastly the village.

    With an additional transformation method to turn a .csv file into .db local database.
    """

    def __init__(self) -> None:
        self._local_db: LocalDBContext | None = None

    # to-do: handle when db folder destination not exist yet
    async def setup_local_db(self, db_url: str) -> None:
        """Must be called once before any other method."""
        if self._local_db is not None:
            logger.warning("setup_local_db() already called")
            return
        engine = create_async_engine(db_url)
        metadata = MetaData()
        location_table = self._define_location_table(metadata)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        self._local_db = LocalDBContext(engine=engine, location_table=location_table)
        logger.debug("setup_local_db() executed")

    async def search_city_or_regency(self, city_or_regency: str) -> list[str]:
        """List all possible cities or regencies based of the given 'city_or_regency' value."""
        db = self._get_local_db()
        escaped = self._escape_string(city_or_regency)
        async with db.engine.connect() as conn:
            stmt = (
                select(db.location_table.c.kabupaten_atau_kota)
                .distinct()
                .where(
                    db.location_table.c.kabupaten_atau_kota.like(
                        f"%{escaped}%", escape="\\"
                    )
                )
            )
            result = (await conn.execute(stmt)).all()
            if not result:
                raise EmptyQueryResultError({"city_or_regency": city_or_regency})
            return [row.kabupaten_atau_kota for row in result]

    async def search_subdistrict(self, city_or_regency: str) -> list[str]:
        """List all the subdistricts of the given city_or_regency name."""
        db = self._get_local_db()
        async with db.engine.connect() as conn:
            stmt = (
                select(db.location_table.c.kecamatan)
                .distinct()
                .where(db.location_table.c.kabupaten_atau_kota == city_or_regency)
            )
            result = (await conn.execute(stmt)).all()
            if not result:
                raise EmptyQueryResultError({"city_or_regency": city_or_regency})
            return [row.kecamatan for row in result]

    async def search_village(self, city_or_regency: str, subdistrict: str) -> list[str]:
        """List all the villages of the given city_or_regency and subdistrict name."""
        db = self._get_local_db()
        async with db.engine.connect() as conn:
            stmt = (
                select(db.location_table.c.desa_atau_kelurahan)
                .distinct()
                .where(
                    (db.location_table.c.kabupaten_atau_kota == city_or_regency)
                    & (db.location_table.c.kecamatan == subdistrict)
                )
            )
            result = (await conn.execute(stmt)).all()
            if not result:
                raise EmptyQueryResultError(
                    {"city_or_regency": city_or_regency, "subdistrict": subdistrict}
                )
            return [row.desa_atau_kelurahan for row in result]

    async def get_adm4_code(
        self, city_or_regency: str, subdistrict: str, village: str
    ) -> str:
        """Get the adm4_code of the given exact location address."""
        db = self._get_local_db()
        async with db.engine.connect() as conn:
            stmt = select(db.location_table.c.kode_adm4).where(
                (db.location_table.c.kabupaten_atau_kota == city_or_regency)
                & (db.location_table.c.kecamatan == subdistrict)
                & (db.location_table.c.desa_atau_kelurahan == village)
            )
            result = (await conn.execute(stmt)).scalar()
            if result is None:
                raise EmptyQueryResultError(
                    {
                        "city_or_regency": city_or_regency,
                        "subdistrict": subdistrict,
                        "village": village,
                    }
                )
            return cast(str, result)

    async def get_full_address(self, adm4_code: str) -> Row[Any]:
        """Get full address of the given adm4_code."""
        db = self._get_local_db()
        async with db.engine.connect() as conn:
            stmt = select(db.location_table).where(
                db.location_table.c.kode_adm4 == adm4_code
            )
            result = (await conn.execute(stmt)).first()
            if result is None:
                raise EmptyQueryResultError({"adm4_code": adm4_code})
            return result

    async def start_csv_to_local_db_transformation(self, csv_filepath: Path) -> None:
        """
        Start the transformation from csv file to sqlite .db database,
        this method should only be called preferably once when the bot server started,
        since the process is slow and blocking.
        """
        db = self._get_local_db()
        logger.info("csv to local db transformation started")
        async with db.engine.begin() as conn:
            for csv_row in self._get_rows_from_csv(csv_filepath):
                await self._insert_or_ignore_location(conn, db.location_table, csv_row)
        logger.info("csv to local db transformation finished")

    async def _insert_or_ignore_location(
        self, conn: AsyncConnection, table: Table, insert_value: CSVLocationDataModel
    ) -> None:
        """
        Insert or ignore the forecast_location table,
        using sqlite specific 'OR IGNORE' dialect to ignore the conflicting row.
        """
        stmt = insert(table).prefix_with("OR IGNORE").values(**insert_value.as_dict())
        result = await conn.execute(stmt)
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

    def _escape_string(self, value: str) -> str:
        return (
            # note: in python string, \\ is equal to \ in pure string
            value.replace("\\", "\\\\")  # replace \ into \\
            .replace("%", "\\%")  # replace % into \%
            .replace("_", "\\_")  # replace _ into \_
        )

    def _define_location_table(self, metadata: MetaData) -> Table:
        return Table(
            "forecast_location",
            metadata,
            Column("kode_adm4", String(), primary_key=True),
            Column("kabupaten_atau_kota", String()),
            Column("kecamatan", String()),
            Column("desa_atau_kelurahan", String()),
        )
