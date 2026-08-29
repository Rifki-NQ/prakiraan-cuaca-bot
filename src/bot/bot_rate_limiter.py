import asyncio
import logging
import time
# Global rate limiter rule: make an object that has internal counter,
# when the internal counter limit hits before the n reset time,
# make the add() method blocks until the counter resets again

logger = logging.getLogger(__name__)


class BotRateLimiter:
    """
    A rate limiter designed to prevent the bot from getting
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

    async def add(self) -> None:
        """
        Increment by 1 to the internal counter,
        if the internal counter hits the limit before the reset time,
        the incoming increment will queue until the next reset.
        """
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
        this method needs to be called as a Task to run it concurrently
        with the add() method.
        """
        logger.info(
            "limit reset timer started, "
            f"increment/add limit: {self._limit} per reset, "
            f"reset interval: every {self._limit_reset_interval} seconds"
        )
        while True:
            await asyncio.sleep(self._limit_reset_interval)  # sleeps for n seconds
            async with self._cond:  # acquire the lock
                self._counter = 0
                self._cond.notify_all()  # notify all wait points
            # release the lock here


class UserRateLimiter:
    """A rate limiter designed to prevent the bot from user spam."""

    def __init__(self, response_cooldown: int) -> None:
        self._response_cooldown = response_cooldown
        self._users_last_acquire: dict[int, float] = {}

    async def acquire(self, chat_id: int) -> None:
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
