import logging
import time
from typing import Any, Self

from src.models.protocols import BotQueryProtocol

logger = logging.getLogger(__name__)


class BotStateHandler:
    OFFSET_STORE_INTERVAL: float = 30

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if cls.OFFSET_STORE_INTERVAL <= 0:
            raise RuntimeError(
                "BotStateHandler.OFFSET_STORE_INTERVAL cannot be less than or equal to 0!"
            )
        return super().__new__(cls)

    def __init__(self, bot_query: BotQueryProtocol) -> None:
        self.query = bot_query
        self._next_offset_store: float | None = None

    async def get_offset(self, bot_token: str) -> int | None:
        """Get offset from db, return None if not found."""
        offset = await self.query.get_bot_offset(bot_token)
        if offset is None:
            logger.info("query returned empty row of bot_offset")
            return None
        return offset.offset if offset.offset is not None else None

    async def store_offset(
        self, bot_token: str, offset: int, force_store: bool = False
    ) -> None:
        """
        Store the offset at most once per OFFSET_STORE_INTERVAL seconds;
        force_store=True bypasses the interval.
        """
        current = time.monotonic()
        if self._can_run(current) or force_store:
            self._next_offset_store = current + self.OFFSET_STORE_INTERVAL
            await self.query.insert_or_update_bot_offset(bot_token, offset)
            logger.debug(f"offset stored: (bot_token: {bot_token}, offset: {offset})")

    def _can_run(self, current: float) -> bool:
        return bool(
            self._next_offset_store is None or current >= self._next_offset_store
        )
