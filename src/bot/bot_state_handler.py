import logging
from datetime import datetime, timedelta
from src.models.protocols import BotQueryProtocol


logger = logging.getLogger(__name__)


class BotStateHandler:
    OFFSET_STORE_INTERVAL = 30

    def __init__(self, query_builder: BotQueryProtocol) -> None:
        self.query = query_builder
        self._last_offset_store: datetime | None = None

    async def get_offset(self, bot_token: str) -> int | None:
        """Get offset from db, return None if not found."""
        offset = await self.query.get_bot_offset(bot_token)
        if offset is None:
            logger.info("query returned empty row of bot_offset")
            return None
        return offset.offset if offset.offset is not None else None

    async def store_offset(self, bot_token: str, offset: int) -> None:
        """Store the offset to db if enough time has passed after the last store."""
        current_datetime = datetime.now()
        if self._can_run(current_datetime):
            self._last_offset_store = current_datetime
            await self.query.insert_or_update_bot_offset(bot_token, offset, current_datetime)
            logger.debug(f"offset store: (bot_token: {bot_token}, offset: {offset})")
        else:
            logger.debug(
                f"skip offset store: (bot_token: {bot_token}, offset: {offset})"
            )

    def _can_run(self, current_datetime: datetime) -> bool:
        """Return True if enough time have passed since self._last_offset_store,
        also return True if self._last_offset_store is still None."""
        if self._last_offset_store is None:
            return True
        interval = current_datetime - self._last_offset_store
        return interval >= timedelta(seconds=self.OFFSET_STORE_INTERVAL)
