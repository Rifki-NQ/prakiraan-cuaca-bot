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

    async def acquire(self) -> None:
        """
        Increment by 1 to the internal counter,
        if the internal counter hits the limit before the reset time,
        the incoming increment will queue until the next reset.
        """
        if not self._reset_time_is_running:
            raise BotThrottlerError("start_reset_timer() has not called yet!")
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

    async def start_reset_timer(self) -> None:
        """
        Start the timer for the internal counter reset,
        this method needs to be called as a Task to make it
        non blocking.
        """
        logger.info(
            "limit reset timer started, "
            f"increment/acquire limit: {self._limit} per reset, "
            f"reset interval: every {self._limit_reset_interval} seconds"
        )
        self._reset_time_is_running = True
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
        self._users_last_acquire: dict[int, float] = {}
        self._delete_stale_data_cycle_is_running = False

    async def acquire(self, chat_id: int) -> None:
        if not self._delete_stale_data_cycle_is_running:
            raise BotThrottlerError(
                "start_delete_stale_data_cycle() has not called yet!"
            )
        last_acquire = self._users_last_acquire.get(chat_id, None)
        if last_acquire is None:
            # save this user last acquire time to the dict
            # then return and let this user continue
            self._users_last_acquire[chat_id] = time.monotonic()
            logger.debug(f"new last acquire data for user {chat_id}")
            return
        current_acquire = time.monotonic()
        # then get the passed time between the two points of acquire
        acquires_interval = current_acquire - last_acquire
        # save the current_acquire to the dict
        self._users_last_acquire[chat_id] = current_acquire
        if acquires_interval < self._response_cooldown:
            # Remaining wait = full cooldown minus time already elapsed
            # since this user's last message. So the wait is dynamic per
            # user, not a fixed delay — someone who's already waited longer
            # gets a shorter sleep, and vice versa.
            sleep_value = self._response_cooldown - acquires_interval
            logger.info(
                f"user {chat_id} rate limited, cooldown for {sleep_value} second"
            )
            await asyncio.sleep(sleep_value)

    async def start_delete_stale_data_cycle(self) -> None:
        """
        Start the cycle of stale data deletion,
        this method needs to be called as a Task to make it
        non blocking.
        """
        self._delete_stale_data_cycle_is_running = True
        while True:
            await asyncio.sleep(self.STALE_DATA_DELETE_CYCLE)
            self._delete_stale_data()

    def _delete_stale_data(self) -> None:
        """
        Delete the stale data by collecting which chat_id
        last_acquire data is stale in a list, then delete it after.
        """
        stale_chat_ids: list[int] = []
        for chat_id, last_acquire in self._users_last_acquire.items():
            if (time.monotonic() - last_acquire) >= 30:
                stale_chat_ids.append(chat_id)
        for chat_id in stale_chat_ids:
            del self._users_last_acquire[chat_id]
        logger.debug(f"stale data deleted, total deleted: {len(stale_chat_ids)}")
