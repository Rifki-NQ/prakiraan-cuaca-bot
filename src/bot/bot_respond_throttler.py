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
        self._waiting_num: int = 0
        self._cond = asyncio.Condition()
        self._reset_timer_is_running = False
        self._reset_timer_task: asyncio.Task[None] | None = None

    async def acquire(self) -> None:
        """
        Increment by 1 to the internal counter,
        if the internal counter hits the limit before the reset time,
        the incoming increment will queue until the next reset.
        """
        if not self._reset_timer_is_running:
            raise BotThrottlerError("start_reset_timer() has not called yet")
        async with self._cond:
            while self._counter >= self._limit:
                self._waiting_num += 1
                try:
                    await self._cond.wait()
                finally:
                    self._waiting_num -= 1
            self._counter += 1

    def start_reset_timer(self) -> None:
        """Start the timer for the internal counter reset."""
        if self._reset_timer_is_running:
            raise BotThrottlerError("start_reset_timer() can only be called once")
        self._reset_timer_is_running = True
        logger.info(
            "limit reset timer started, "
            f"increment/acquire limit: {self._limit} per reset, "
            f"reset interval: every {self._limit_reset_interval} seconds"
        )
        task = asyncio.create_task(self._run_reset_loop())
        task.set_name("global-throttler-reset-timer-task")
        self._reset_timer_task = task

    async def stop_reset_timer(self) -> None:
        """
        Stop or cancel the reset timer background task then
        modify the state of self._reset_timer_is_running to False
        and self._reset_timer_task to None.

        This method also make sure all waiters of acquire() method
        to finish before stopping the reset timer.
        """
        if not self._reset_timer_is_running:
            raise BotThrottlerError("reset timer is not running, no need to stop")
        assert isinstance(self._reset_timer_task, asyncio.Task), (
            "self._reset_timer_task should always be asyncio.Task[None], "
            "when self._reset_timer_is_running is True"
        )
        self._reset_timer_task.cancel()
        try:
            await self._reset_timer_task
        except asyncio.CancelledError:
            logger.debug(f"{self._reset_timer_task.get_name()} cancelled")
        except Exception as e:
            logger.error("reset timer task ended unexpectedly", exc_info=e)
            raise
        finally:
            # flips the state of self._reset_timer_is_running to False first
            # for the purpose of no acquire() while the waiters are drained
            self._reset_timer_is_running = False
            await self._drain_waiters()
            self._reset_timer_task = None
            logger.debug("reset timer stopped")

    async def _run_reset_loop(self) -> None:
        while True:
            await asyncio.sleep(self._limit_reset_interval)
            async with self._cond:
                self._counter = 0
                self._cond.notify_all()

    async def _drain_waiters(self) -> None:
        """
        Drain remained waiters while still adding intervals
        between each reset window.
        """
        while self._waiting_num > 0:
            await asyncio.sleep(self._limit_reset_interval)
            async with self._cond:
                logger.debug(f"draining remained waiters: {self._waiting_num}")
                self._counter = 0
                self._cond.notify_all()


class UserRespondThrottler:
    """A throttler designed to prevent the bot from user spam."""

    STALE_DATA_DELETE_CYCLE: float = 60  # check then delete stale data every n second
    DATA_STALE_AFTER_SECONDS: float = 30  # data older than this is considered stale

    def __init__(self, response_cooldown: float) -> None:
        self._response_cooldown = response_cooldown
        self._users_next_slot: dict[int, float] = {}
        self._delete_stale_data_cycle_is_running = False
        self._delete_stale_data_cycle_task: asyncio.Task[None] | None = None

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
        logger.debug(f"user {chat_id} throttled, cooldown for {wait_time:.2f} second")
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
        self._delete_stale_data_cycle_task = task

    async def stop_delete_stale_data_cycle(self) -> None:
        if not self._delete_stale_data_cycle_is_running:
            raise BotThrottlerError(
                "delete stale data cycle is not running, no need to stop"
            )
        assert isinstance(self._delete_stale_data_cycle_task, asyncio.Task), (
            "self._delete_stale_data_cycle_task should always be asyncio.Task[None], "
            "when self._delete_stale_data_cycle_is_running is True"
        )
        self._delete_stale_data_cycle_task.cancel()
        try:
            await self._delete_stale_data_cycle_task
        except asyncio.CancelledError:
            logger.debug(f"{self._delete_stale_data_cycle_task.get_name()} cancelled")
        except Exception as e:
            logger.error("delete stale data cycle task ended unexpectedly", exc_info=e)
            raise
        finally:
            self._delete_stale_data_cycle_is_running = False
            # clear users_next_slot data by assigning new dict to it
            self._users_next_slot = {}
            self._delete_stale_data_cycle_task = None
            logger.debug("delete stale data cycle stopped")

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
                # is more than n second relative to when this runs
                if (time.monotonic() - last_acquire) > self.DATA_STALE_AFTER_SECONDS:
                    stale_chat_ids.append(chat_id)
            for chat_id in stale_chat_ids:
                del self._users_next_slot[chat_id]
            logger.debug(f"stale data deleted, total deleted: {len(stale_chat_ids)}")
