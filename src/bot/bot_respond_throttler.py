import asyncio
import logging
import time
from src.exceptions import BotThrottlerError


logger = logging.getLogger(__name__)


class GlobalRespondThrottler:
    """
    A throttler designed to prevent the bot from getting
    itself rate limited by telegram,
    by keeping the Bot.send_message to all chats under n times each second.
    """

    def __init__(
        self,
        limit: int,  # decide the limit of the increments until next window
        limit_reset_interval: int,  # decide the interval time of 'limit' reset
    ) -> None:
        self._limit = limit
        self._limit_reset_interval = limit_reset_interval
        self._counter: int = 0  # initial counter value is 0
        self._cond = asyncio.Condition()
        self._reset_time_is_running = False
        self._background_timer_task: asyncio.Task[None] | None = None

    async def acquire(self) -> None:
        """
        Increment by 1 to the internal counter,
        if the internal counter hits the limit before the reset time,
        the incoming increment will queue until the next reset.
        """
        if not self._reset_time_is_running:
            raise BotThrottlerError("start_reset_timer() has not called yet")
        async with self._cond:  # acquire the lock
            # check if counter has reached limit,
            # recheck again even after self._cond.notify_all() by the timer
            while self._counter >= self._limit:
                await (
                    self._cond.wait()
                )  # release the lock then wait here until notified
                # after notified, re-acquire the lock
                # then recheck the condition of the _counter
                # if the _counter is >= self._limit, wait again until next notify
            self._counter += 1  # increment the counter by one
        # release the lock here

    def start_reset_timer(self) -> None:
        """Start the timer for the internal counter reset."""
        if self._reset_time_is_running:
            raise BotThrottlerError("start_reset_timer() can only be called once")
        self._reset_time_is_running = True
        logger.info(
            "limit reset timer started, "
            f"increment/acquire limit: {self._limit} per reset, "
            f"reset interval: every {self._limit_reset_interval} seconds"
        )
        task = asyncio.create_task(self._run_reset_loop())
        task.set_name("global-throttler-reset-timer-task")
        self._background_timer_task = task

    async def _run_reset_loop(self) -> None:
        while True:
            await asyncio.sleep(self._limit_reset_interval)  # sleeps for n seconds
            async with self._cond:  # acquire the lock
                self._counter = 0
                self._cond.notify_all()  # notify all wait points
            # release the lock here


class UserRespondThrottler:
    """A throttler designed to prevent the bot from user spam."""

    STALE_DATA_DELETE_CYCLE = 60  # every 60 seconds

    def __init__(self, response_cooldown: int) -> None:
        self._response_cooldown = response_cooldown
        self._users_next_slot: dict[int, float] = {}
        self._delete_stale_data_cycle_is_running = False
        self._background_stale_data_deletion_task: asyncio.Task[None] | None = None

    async def acquire(self, chat_id: int) -> None:
        if not self._delete_stale_data_cycle_is_running:
            raise BotThrottlerError(
                "start_delete_stale_data_cycle() has not called yet"
            )
        now = time.monotonic()
        next_slot = self._users_next_slot.get(chat_id, now)
        if now >= next_slot:
            self._users_next_slot[chat_id] = now + self._response_cooldown
            return
        wait_time = next_slot - now
        self._users_next_slot[chat_id] = next_slot + self._response_cooldown
        logger.debug(f"user {chat_id} throttled, cooldown for {wait_time}")
        await asyncio.sleep(wait_time)

    def start_delete_stale_data_cycle(self) -> None:
        """Start the cycle of stale data deletion."""
        if self._delete_stale_data_cycle_is_running:
            raise BotThrottlerError(
                "start_delete_stale_data_cycle() can only be called once"
            )
        self._delete_stale_data_cycle_is_running = True
        task = asyncio.create_task(self._run_delete_stale_data_loop())
        task.set_name("user-throttler-stale-data-deletion-task")
        self._background_stale_data_deletion_task = task

    async def _run_delete_stale_data_loop(self) -> None:
        """
        Delete the stale data by collecting which chat_id
        last_acquire data is stale in a list, then delete it after.
        """
        while True:
            await asyncio.sleep(self.STALE_DATA_DELETE_CYCLE)
            stale_chat_ids: list[int] = []
            for chat_id, last_acquire in self._users_next_slot.items():
                # consider the data as stale when this user last_acquire data
                # is more than 30 seconds old relative to now
                if (time.monotonic() - last_acquire) > 30:
                    stale_chat_ids.append(chat_id)
            for chat_id in stale_chat_ids:
                del self._users_next_slot[chat_id]
            logger.debug(f"stale data deleted, total deleted: {len(stale_chat_ids)}")
