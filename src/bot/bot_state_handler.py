import logging
from datetime import datetime, timedelta
from src.models.protocols import QueryBuilderProtocol


logger = logging.getLogger(__name__)


class BotStateHandler:
    OFFSET_STORE_INTERVAL = 30

    def __init__(self, query_builder: QueryBuilderProtocol) -> None:
        self.query = query_builder
        self._last_offset_store: datetime | None = None

    async def get_offset(self, bot_token: str) -> int | None:
        """Get offset from db, return None if not found"""
        current_offset = await self.query.get_bot_offset(bot_token)
        if current_offset is None:
            logger.info("Query return empty row of bot_offset")
            return None
        return current_offset.offset

    async def store_offset(self, bot_token: str, offset: int) -> None:
        """Store the offset to db if enough time has passed after the last store"""
        current_datetime = datetime.now()
        if self._can_run(current_datetime):
            self._last_offset_store = current_datetime
            await self.query.store_bot_offset(bot_token, offset, current_datetime)
            logger.debug(f"offset store: (bot_token: {bot_token}, offset: {offset})")
        else:
            logger.debug(
                f"skip offset store: (bot_token: {bot_token}, offset: {offset})"
            )

    def _can_run(self, current_datetime: datetime) -> bool:
        if self._last_offset_store is None:
            return True
        interval = current_datetime - self._last_offset_store
        return interval >= timedelta(seconds=self.OFFSET_STORE_INTERVAL)
