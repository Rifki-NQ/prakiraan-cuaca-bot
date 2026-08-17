from sqlalchemy import MetaData, inspect
from sqlalchemy.ext.asyncio import AsyncEngine


async def drop_all_tables(engine: AsyncEngine) -> None:
    """Drop all tables of a database."""
    metadata = MetaData()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.reflect)
        await conn.run_sync(metadata.drop_all)


async def get_tables_name(engine: AsyncEngine) -> list[str]:
    """Return list of table names from a database."""
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
