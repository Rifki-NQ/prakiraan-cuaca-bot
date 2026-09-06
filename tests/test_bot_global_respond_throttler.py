import pytest
import pytest_asyncio
import asyncio
from collections.abc import AsyncGenerator
import contextlib
import time
from src.bot.bot_respond_throttler import GlobalRespondThrottler
from src.exceptions import BotThrottlerError


@pytest.fixture
def limit(request: pytest.FixtureRequest) -> int:
    return request.param


@pytest.fixture
def limit_reset_interval(request: pytest.FixtureRequest) -> int:
    return request.param


@pytest_asyncio.fixture
async def global_respond_throttler(
    limit: int, limit_reset_interval: int
) -> AsyncGenerator[GlobalRespondThrottler, None]:
    throttler = GlobalRespondThrottler(limit, limit_reset_interval)
    throttler.start_reset_timer()
    task = throttler._background_timer_task  # pyright: ignore[reportPrivateUsage]
    assert task is not None
    try:
        yield throttler
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.parametrize("limit, limit_reset_interval", [(30, 0.5)], indirect=True)
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
        max_counter = max(global_respond_throttler._counter, max_counter)  # pyright: ignore[reportPrivateUsage]
        await global_respond_throttler.acquire()
    assert max_counter == global_respond_throttler._limit  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("limit, limit_reset_interval", [(10, 1)], indirect=True)
async def test_global_throttler_acquire_suspends_before_reset(
    global_respond_throttler: GlobalRespondThrottler,
) -> None:
    """
    Test that global_respond_throttler.acquire() suspends
    when it reached the internal counter limit,
    this test case uses pytest.approx() to assert that n second
    has really passed after the counter reset, which trigger
    the acquire() to continue.
    """
    before_suspends = time.monotonic()
    for _ in range(11):  # slightly above the limit value
        await global_respond_throttler.acquire()
    after_suspends = time.monotonic()
    suspended_time = after_suspends - before_suspends
    assert pytest.approx(suspended_time, rel=0.01) == 1


@pytest.mark.parametrize("limit, limit_reset_interval", [(30, 1)], indirect=True)
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
        # run this if 1 second has passed after the last acquire()
        if (time.monotonic() - last_acquire_time) > 1:
            # assert to 1, since the acquire() mechanism is:
            # suspends if the limit reached,
            # then continue incrementing
            reset_to_zero = global_respond_throttler._counter == 1  # pyright: ignore[reportPrivateUsage]
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
