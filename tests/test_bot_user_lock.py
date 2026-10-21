# pyright: reportPrivateUsage=false
import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress

import pytest

from src.bot.bot_user_lock import BotUserLock


async def cancel_task(task: asyncio.Task[None]) -> None:
    """
    Cancel a task then waits until the cancellation
    is finished
    """
    try:
        task.cancel()
    finally:
        with suppress(BaseException):
            await task


@pytest.fixture
def bot_user_lock() -> BotUserLock:
    return BotUserLock()


async def simulate_users_traffic(
    bot_user_lock: BotUserLock,
    incoming_chat_id: int,
    tracker: Callable[[], Awaitable[None]],
) -> None:
    async with bot_user_lock.user_lock(chat_id=incoming_chat_id):
        await tracker()


@pytest.mark.parametrize(
    "incoming_chat_ids, expected_max_concurrency",
    [([1, 2, 3, 4, 5], 5), ([1, 1, 1, 1, 1], 1)],
    ids=["different_users", "same_user"],
)
async def test_max_concurrency(
    bot_user_lock: BotUserLock,
    incoming_chat_ids: list[int],
    expected_max_concurrency: int,
) -> None:
    tasks: set[asyncio.Task[None]] = set()
    in_flight = 0
    peak = 0

    async def _track() -> None:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        try:
            await asyncio.sleep(0.01)
        finally:
            in_flight -= 1

    for i in incoming_chat_ids:
        tasks.add(
            asyncio.create_task(
                simulate_users_traffic(
                    bot_user_lock=bot_user_lock, incoming_chat_id=i, tracker=_track
                )
            )
        )
    await asyncio.sleep(0)  # yields control
    assert peak == expected_max_concurrency
    # cancel all tasks
    for task in tasks:
        await cancel_task(task)


async def test_lock_removed_when_unused(bot_user_lock: BotUserLock) -> None:
    release = asyncio.Event()

    async def _blocked_until_release() -> None:
        await release.wait()

    async def _simulate_traffic(blocker: Callable[[], Awaitable[None]]) -> None:
        async with bot_user_lock.user_lock(chat_id=1):
            await blocker()

    task = asyncio.create_task(_simulate_traffic(blocker=_blocked_until_release))
    await asyncio.sleep(0)  # yields control
    # assert there is a lock in the self._locks
    assert len(bot_user_lock._locks) == 1
    # release the blocker,
    # which makes the lock reference goes to 0
    release.set()
    # assert the lock was deleted
    await asyncio.sleep(0)  # yields control
    assert len(bot_user_lock._locks) == 0

    await cancel_task(task)
