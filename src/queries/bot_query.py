import logging
from typing import Any
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
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.dialects.postgresql import insert
from src.service import BOT_DATETIME
from src.models.contexts import BotDBContext
from src.models.domain_model import UserDataModel
from src.exceptions import DBNotInitializedError

logger = logging.getLogger(__name__)


class BotQuery:
    def __init__(self) -> None:
        self._db: BotDBContext | None = None

    async def setup_bot_db(self, db_url: str) -> None:
        """Must be called first before any other method."""
        engine = create_async_engine(db_url, pool_pre_ping=True)
        metadata = MetaData()
        bot_offset_table = self._define_bot_offset_table(metadata)
        bot_user_table = self._define_bot_user_table(metadata)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        self._db = BotDBContext(
            engine=engine,
            bot_offset_table=bot_offset_table,
            bot_user_table=bot_user_table,
        )
        logger.debug("setup_bot_db() executed")

    async def get_bot_offset(self, bot_token: str) -> Row[Any] | None:
        """Get or select bot_offset data if it exists."""
        db = self._get_db()
        async with db.engine.connect() as conn:
            stmt = select(db.bot_offset_table).where(
                db.bot_offset_table.c.bot_token == bot_token
            )
            result = await conn.execute(stmt)
            return result.fetchone()

    async def insert_or_update_bot_offset(
        self, bot_token: str, offset: int, update_time: datetime
    ) -> None:
        """Insert or update bot_offset data except the pk."""
        db = self._get_db()
        async with db.engine.begin() as conn:
            stmt = insert(db.bot_offset_table).values(
                bot_token=bot_token, offset=offset, updated_at=update_time
            )
            pk_names = {pk.name for pk in db.bot_offset_table.primary_key.c}
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=pk_names,
                set_={
                    col.name: stmt.excluded[col.name]
                    for col in db.bot_offset_table.c
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
        pk_names = {pk.name for pk in db.bot_user_table.primary_key.c}
        excluded_columns = {"created_at", *pk_names}

        async with db.engine.begin() as conn:
            stmt = insert(db.bot_user_table).values(
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
                    for col in db.bot_user_table.c
                    if col.name not in excluded_columns
                },
            ).returning(db.bot_user_table.c.created_at)
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
            stmt = select(db.bot_user_table).where(
                db.bot_user_table.c.chat_id == chat_id
            )
            result = await conn.execute(stmt)
            return result.fetchone()

    def _get_current_datetime(self) -> datetime:
        """Get current datetime with datetime.now() in Asia/Jakarta timezone,
        with the tzinfo removed."""
        current_datetime = datetime.now(tz=BOT_DATETIME)
        return current_datetime.replace(tzinfo=None)

    def _get_db(self) -> BotDBContext:
        """get the db attributes, can be called after setup_bot_db()."""
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

    def _define_bot_user_table(self, metadata: MetaData) -> Table:
        return Table(
            "bot_user",
            metadata,
            Column("chat_id", Integer(), primary_key=True),
            Column("username", String(), nullable=True),
            Column("adm4_code", String()),
            Column("updated_at", DateTime()),
            Column("created_at", DateTime()),
        )
