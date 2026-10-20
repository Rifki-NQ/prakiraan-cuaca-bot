import asyncio
import weakref
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class BotUserLock:
    """Used to prevent concurrent bot respond for each specific user"""

    def __init__(self) -> None:
        self._locks: weakref.WeakValueDictionary[int, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    @asynccontextmanager
    async def user_lock(self, chat_id: int) -> AsyncGenerator[None, None]:
        """Acquire the lock for a user"""
        lock = self._locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            yield
