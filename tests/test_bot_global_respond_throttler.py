# pyright: reportPrivateUsage=false
import pytest
import pytest_asyncio
from unittest.mock import patch
import asyncio
from collections.abc import AsyncGenerator
import contextlib
import time
from src.bot.bot_respond_throttler import GlobalRespondThrottler
from src.exceptions import BotThrottlerError


@pytest.fixture
def limit(request: pytest.FixtureRequest) -> int:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def limit_reset_interval(request: pytest.FixtureRequest) -> int:
    return request.param  # type: ignore[no-any-return]


@pytest_asyncio.fixture
async def global_respond_throttler(
    limit: int, limit_reset_interval: int
) -> AsyncGenerator[GlobalRespondThrottler, None]:
    throttler = GlobalRespondThrottler(limit, limit_reset_interval)
    throttler.start_reset_timer()
    task = throttler._reset_timer_task
    assert task is not None
    try:
        yield throttler
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.parametrize("limit, limit_reset_interval", [(30, 0.1)], indirect=True)
async def test_global_throttler_max_counter_value(
    global_respond_throttler: GlobalRespondThrottler,
) -> None:
    """
    Test that global_respond_throttler.acquire() stops
    incrementing to the internal counter when it reached
    the limit.
    """
    max_counter = 0
    for _ in range(31):  # slightly above the limit value
        max_counter = max(global_respond_throttler._counter, max_counter)
        await global_respond_throttler.acquire()
    assert max_counter == global_respond_throttler._limit


@pytest.mark.parametrize("limit, limit_reset_interval", [(10, 0.2)], indirect=True)
async def test_global_throttler_acquire_suspends_before_reset(
    global_respond_throttler: GlobalRespondThrottler,
) -> None:
    """
    Test that global_respond_throttler.acquire() suspends
    when it reached the internal counter limit,
    this test case uses pytest.approx() to assert that 0.2 second
    has really passed after the counter reset, which trigger
    the acquire() to continue.
    """
    before_suspends = time.monotonic()
    for _ in range(11):  # slightly above the limit value
        await global_respond_throttler.acquire()
    after_suspends = time.monotonic()
    suspended_time = after_suspends - before_suspends
    assert pytest.approx(suspended_time, rel=0.01) == 0.2


@pytest.mark.parametrize("limit, limit_reset_interval", [(30, 0.2)], indirect=True)
async def test_global_throttler_counter_resets(
    global_respond_throttler: GlobalRespondThrottler,
) -> None:
    """
    Test that the internal counter goes back to 0
    after it hits limit then get reset by the timer.
    """
    reset_to_zero = False
    for _ in range(31):  # slightly above the limit value
        last_acquire_time = time.monotonic()
        await global_respond_throttler.acquire()
        # run this if 0.2 second has passed after the last acquire()
        if (time.monotonic() - last_acquire_time) > 0.2:
            # assert to 1, since the acquire() mechanism is:
            # suspends if the limit reached,
            # then continue incrementing
            reset_to_zero = global_respond_throttler._counter == 1
    assert reset_to_zero


async def test_global_throttler_raise_when_acquire_before_timer_start() -> None:
    global_respond_throttler = GlobalRespondThrottler(1, 1)
    with pytest.raises(BotThrottlerError) as exc_info:
        await global_respond_throttler.acquire()
    assert "has not called yet" in exc_info.value.args[0]


@pytest.mark.parametrize("limit, limit_reset_interval", [(1, 0.1)], indirect=True)
async def test_global_throttler_raise_when_timer_called_twice(
    global_respond_throttler: GlobalRespondThrottler,
) -> None:
    # this test case uses the throttler fixture,
    # since it already started the timer as a Task
    with pytest.raises(BotThrottlerError) as exc_info:
        global_respond_throttler.start_reset_timer()
    assert "can only be called once" in exc_info.value.args[0]


class TestStopResetTimer:
    async def cancel_tasks(self, tasks: list[asyncio.Task[None]]) -> None:
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    @pytest.mark.parametrize("limit, limit_reset_interval", [(1, 0.1)], indirect=True)
    async def test_timer_stopped(
        self, global_respond_throttler: GlobalRespondThrottler
    ) -> None:
        """
        Test that stop_reset_timer() cancel the reset timer Task
        and reset the states
        """
        # assert the task is running before the test
        assert global_respond_throttler._reset_timer_is_running
        assert isinstance(global_respond_throttler._reset_timer_task, asyncio.Task)
        task = global_respond_throttler._reset_timer_task

        await global_respond_throttler.stop_reset_timer()

        assert not global_respond_throttler._reset_timer_is_running
        assert global_respond_throttler._reset_timer_task is None
        assert task.done()

    @pytest.mark.parametrize("limit, limit_reset_interval", [(30, 0.2)], indirect=True)
    async def test_remaining_waiters_cleared(
        self, global_respond_throttler: GlobalRespondThrottler
    ) -> None:
        total_acquires = 65
        successful_acquire = 0

        async def _tracked_acquire(
            global_respond_throttler: GlobalRespondThrottler,
        ) -> None:
            nonlocal successful_acquire
            await global_respond_throttler.acquire()
            successful_acquire += 1

        tasks = [
            asyncio.create_task(_tracked_acquire(global_respond_throttler))
            for _ in range(total_acquires)
        ]
        await asyncio.sleep(0)  # let the tasks runs
        # the acquires should be capped to the limit value here
        # because reset_timer has not reset it yet
        assert successful_acquire == 30
        # stop_reset_timer() then will stop the reset_timer task
        # then call _drain_waiters(), which will drain remained waiters
        # while still adding intervals between each reset window
        await global_respond_throttler.stop_reset_timer()
        assert successful_acquire == total_acquires

        await self.cancel_tasks(tasks)

    async def test_when_the_timer_ended_unexpectedly(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(40)  # level: ERROR
        global_respond_throttler = GlobalRespondThrottler(
            limit=30, limit_reset_interval=1
        )
        # simulate _run_reset_loop raises unexpected error
        with patch.object(
            global_respond_throttler,
            "_run_reset_loop",
            side_effect=RuntimeError("fake unexpected error"),
        ):
            global_respond_throttler.start_reset_timer()
            await asyncio.sleep(0)
        with pytest.raises(RuntimeError):
            await global_respond_throttler.stop_reset_timer()
        assert "reset timer task ended unexpectedly" in caplog.messages[0]

    async def test_stop_when_reset_timer_is_not_running(
        self,
    ) -> None:
        global_respond_throttler = GlobalRespondThrottler(
            limit=30, limit_reset_interval=1
        )
        with pytest.raises(BotThrottlerError):
            await global_respond_throttler.stop_reset_timer()

    @pytest.mark.parametrize("limit, limit_reset_interval", [(1, 0.1)], indirect=True)
    async def test_acquire_after_stop_reset_timer(
        self, global_respond_throttler: GlobalRespondThrottler
    ) -> None:
        await global_respond_throttler.stop_reset_timer()
        with pytest.raises(BotThrottlerError):
            await global_respond_throttler.acquire()
