from dataclasses import dataclass
from sqlalchemy import Table, Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from src.models.commands import Commands


@dataclass
class BotUpdateContext:
    chat_id: int
    command: Commands


@dataclass
class DBContext:
    engine: AsyncEngine
    location_table: Table
    forecast_table: Table
    offset_table: Table
    user_table: Table


@dataclass
class LocalDBContext:
    engine: Engine
    location_table: Table
