from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncConnection


async def drop_all_tables(conn: AsyncConnection) -> None:
    metadata = MetaData()
    await conn.run_sync(metadata.reflect)
    await conn.run_sync(metadata.drop_all)
