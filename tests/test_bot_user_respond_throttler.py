import pytest
import pytest_asyncio
import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from src.bot.bot_respond_throttler import UserRespondThrottler
from src.exceptions import BotThrottlerError


FAKE_CHAT_ID = 123


@pytest.fixture
def response_cooldown(request: pytest.FixtureRequest) -> int:
    try:
        response_cooldown = request.param
    except AttributeError:
        # default to 1 if there is no response_cooldown provided
        # by pytest.mark.parametrize (indirect=True)
        response_cooldown = 1
    return response_cooldown


@pytest_asyncio.fixture
async def user_respond_throttler(
    response_cooldown: int,
) -> AsyncGenerator[UserRespondThrottler, None]:
    throttler = UserRespondThrottler(response_cooldown)
    throttler.start_delete_stale_data_cycle()
    task = throttler._background_stale_data_deletion_task  # pyright: ignore[reportPrivateUsage]
    assert task is not None
    try:
        yield throttler
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def test_acquire_when_user_has_no_next_slot(
    user_respond_throttler: UserRespondThrottler, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that acquire() doesn't suspends when there is no
    next_slot value in the dict for a specific user.
    """
    caplog.set_level(10)
    before = time.monotonic()
    await user_respond_throttler.acquire(FAKE_CHAT_ID)
    after = time.monotonic()
    assert (after - before) < 0.0001
    assert not caplog.messages


async def test_acquire_when_user_has_next_slot(
    user_respond_throttler: UserRespondThrottler, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that acquire() suspends when user has a next_slow
    value in the dict.
    """
    caplog.set_level(10)
    before = time.monotonic()
    # first acquire, does not suspends
    await user_respond_throttler.acquire(FAKE_CHAT_ID)
    # second acquire, suspends
    await user_respond_throttler.acquire(FAKE_CHAT_ID)
    after = time.monotonic()
    assert (after - before) == pytest.approx(1, rel=0.01)
    assert "cooldown for 1.00 second" in caplog.messages[0]


@pytest.mark.parametrize("response_cooldown", [0.2], indirect=True)
async def test_acquire_when_user_send_burst_message(
    user_respond_throttler: UserRespondThrottler, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test that acquire() put expected suspends time
    when there is burst of incoming updates from a specific user.
    """
    before = time.monotonic()
    for _ in range(5):  # 5 burst incoming acquire() scenario
        task = asyncio.create_task(user_respond_throttler.acquire(FAKE_CHAT_ID))
        await task
    after = time.monotonic()
    # assert 5 burst message is equal to 0.8 second (with 0.2 cooldowns)
    # since first acquire does not suspends (no next_slot value yet)
    assert (after - before) == pytest.approx(0.8, rel=0.01)


async def test_acquire_when_start_delete_stale_data_cycle_has_not_called_yet() -> None:
    throttler = UserRespondThrottler(1)
    with pytest.raises(BotThrottlerError) as exc_info:
        await throttler.acquire(FAKE_CHAT_ID)
    assert "not called yet" in exc_info.value.args[0]


async def test_start_delete_stale_data_cycle_create_task() -> None:
    throttler = UserRespondThrottler(1)
    assert not throttler._delete_stale_data_cycle_is_running  # pyright: ignore[reportPrivateUsage]
    assert throttler._background_stale_data_deletion_task is None  # pyright: ignore[reportPrivateUsage]
    throttler.start_delete_stale_data_cycle()
    await asyncio.sleep(0)  # yields control to the event loop to run the task
    assert throttler._delete_stale_data_cycle_is_running  # pyright: ignore[reportPrivateUsage]
    assert isinstance(throttler._background_stale_data_deletion_task, asyncio.Task)  # pyright: ignore[reportPrivateUsage]
    assert (
        throttler._background_stale_data_deletion_task.get_name()  # pyright: ignore[reportPrivateUsage]
        == "user-throttler-stale-data-deletion-task"
    )


async def test_start_delete_stale_data_cycle_raise_when_called_twice() -> None:
    throttler = UserRespondThrottler(1)
    throttler.start_delete_stale_data_cycle()
    await asyncio.sleep(0)  # yields control to the event loop to run the task
    with pytest.raises(BotThrottlerError) as exc_info:
        throttler.start_delete_stale_data_cycle()
    assert "can only be called once" in exc_info.value.args[0]


async def test_run_delete_stale_data_loop_delete_stale_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(10)
    throttler = UserRespondThrottler(1)
    throttler.STALE_DATA_DELETE_CYCLE = 2
    throttler.DATA_STALE_AFTER_SECONDS = 1
    throttler.start_delete_stale_data_cycle()
    await throttler.acquire(1)
    await throttler.acquire(2)
    # create a scenario where user 3 data is not considered stale yet
    await asyncio.sleep(0.1)  # sleeps for 0.1 second then acquire()
    await throttler.acquire(3)
    await asyncio.sleep(2.3)
    assert "total deleted: 2" in caplog.messages[0]
