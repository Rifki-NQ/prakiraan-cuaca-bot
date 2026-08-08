from dataclasses import dataclass
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine
from src.models.enums import Commands, UserLocationState
from src.models.domain_model import BotUserStateModel


@dataclass
class BotUpdateContext:
    chat_id: int
    command: Commands
    command_value: str | None = None


@dataclass
class ETLDBContext:
    engine: AsyncEngine
    location_table: Table
    forecast_table: Table


@dataclass
class BotDBContext:
    engine: AsyncEngine
    bot_offset_table: Table
    bot_user_table: Table
    bot_user_state_table: Table


@dataclass
class LocalDBContext:
    engine: AsyncEngine
    location_table: Table


@dataclass
class BotUserStateContext:
    user_location_state: UserLocationState
    bot_user_state: BotUserStateModel | None
