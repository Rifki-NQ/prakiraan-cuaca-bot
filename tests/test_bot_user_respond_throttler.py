# pyright: reportPrivateUsage=false
import pytest
import pytest_asyncio
from unittest.mock import patch
import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from src.bot.bot_respond_throttler import UserRespondThrottler
from src.exceptions import BotThrottlerError


FAKE_CHAT_ID = 1
DEFAULT_COOLDOWN = 0.1


@pytest.fixture
def response_cooldown(request: pytest.FixtureRequest) -> int:
    try:
        response_cooldown = request.param
    except AttributeError:
        # default to 0.1 if there is no response_cooldown provided
        # by pytest.mark.parametrize (indirect=True)
        response_cooldown = DEFAULT_COOLDOWN
    return response_cooldown  # type: ignore[no-any-return]


@pytest_asyncio.fixture
async def user_respond_throttler(
    response_cooldown: int,
) -> AsyncGenerator[UserRespondThrottler, None]:
    throttler = UserRespondThrottler(response_cooldown)
    throttler.start_delete_stale_data_cycle()
    task = throttler._delete_stale_data_cycle_task
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
    assert (after - before) == pytest.approx(DEFAULT_COOLDOWN, rel=0.01)
    assert f"cooldown for {DEFAULT_COOLDOWN:.2f} second" in caplog.messages[0]


@pytest.mark.parametrize("response_cooldown", [0.2], indirect=True)
async def test_acquire_when_user_send_burst_message(
    user_respond_throttler: UserRespondThrottler,
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
    throttler = UserRespondThrottler(DEFAULT_COOLDOWN)
    with pytest.raises(BotThrottlerError) as exc_info:
        await throttler.acquire(FAKE_CHAT_ID)
    assert "not called yet" in exc_info.value.args[0]


async def test_start_delete_stale_data_cycle_create_task() -> None:
    throttler = UserRespondThrottler(DEFAULT_COOLDOWN)
    assert not throttler._delete_stale_data_cycle_is_running
    assert throttler._delete_stale_data_cycle_task is None
    throttler.start_delete_stale_data_cycle()
    await asyncio.sleep(0)  # yields control to the event loop to run the task
    assert throttler._delete_stale_data_cycle_is_running
    assert isinstance(throttler._delete_stale_data_cycle_task, asyncio.Task)
    assert (
        throttler._delete_stale_data_cycle_task.get_name()
        == "user-throttler-stale-data-deletion-task"
    )


async def test_start_delete_stale_data_cycle_raise_when_called_twice() -> None:
    throttler = UserRespondThrottler(1)
    throttler.start_delete_stale_data_cycle()
    await asyncio.sleep(0)  # yields control to the event loop to run the task
    with pytest.raises(BotThrottlerError) as exc_info:
        throttler.start_delete_stale_data_cycle()
    assert "can only be called once" in exc_info.value.args[0]


async def test_run_delete_stale_data_loop_deletes_stale_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(10)
    throttler = UserRespondThrottler(DEFAULT_COOLDOWN)
    throttler.STALE_DATA_DELETE_CYCLE = 0.3
    throttler.DATA_STALE_AFTER_SECONDS = 0.2
    throttler.start_delete_stale_data_cycle()
    await asyncio.sleep(0)  # let the delete_stale_data_cycle task run
    await throttler.acquire(1)  # first acquire
    await throttler.acquire(2)  # second acquire
    # create a scenario where user 3 data is not considered stale yet
    await asyncio.sleep(0.1)  # sleeps for 0.1 second then acquire()
    await throttler.acquire(3)  # third acquire
    await asyncio.sleep(0.3)
    assert "total deleted: 2" in caplog.messages[0]


class TestStopDeleteStaleDataCycle:
    async def cancel_tasks(self, tasks: list[asyncio.Task[None]]) -> None:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def test_task_stopped(
        self, user_respond_throttler: UserRespondThrottler
    ) -> None:
        """
        Test that stop_delete_stale_data_cycle() cancel the
        self._delete_stale_data_cycle_task task
        and flip the states:
        _delete_stale_data_cycle_task to None and
        _delete_stale_data_cycle_is_running to False
        """
        assert user_respond_throttler._delete_stale_data_cycle_is_running
        assert isinstance(
            user_respond_throttler._delete_stale_data_cycle_task, asyncio.Task
        )
        task = user_respond_throttler._delete_stale_data_cycle_task

        await user_respond_throttler.stop_delete_stale_data_cycle()

        assert not user_respond_throttler._delete_stale_data_cycle_is_running
        assert user_respond_throttler._delete_stale_data_cycle_task is None
        assert task.done()

    async def test_next_slot_data_cleared(
        self, user_respond_throttler: UserRespondThrottler
    ) -> None:
        """
        Test that self._users_next_slot dict is cleared after
        stop_delete_stale_data_cycle() was called
        """
        total_acquires = 10
        tasks = [
            asyncio.create_task(user_respond_throttler.acquire(i))
            for i in range(total_acquires)
        ]
        await asyncio.sleep(0)

        assert len(user_respond_throttler._users_next_slot) == total_acquires
        await user_respond_throttler.stop_delete_stale_data_cycle()
        assert len(user_respond_throttler._users_next_slot) == 0

        await self.cancel_tasks(tasks)

    async def test_when_the_delete_stale_data_cycle_task_ended_unexpectedly(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(40)  # level: ERROR
        user_respond_throttler = UserRespondThrottler(
            response_cooldown=DEFAULT_COOLDOWN
        )
        # simulate _run_delete_stale_data_loop raises unexpected error
        with patch.object(
            user_respond_throttler,
            "_run_delete_stale_data_loop",
            side_effect=RuntimeError("fake unexpected error"),
        ):
            user_respond_throttler.start_delete_stale_data_cycle()
            await asyncio.sleep(0)
        with pytest.raises(RuntimeError):
            await user_respond_throttler.stop_delete_stale_data_cycle()
        assert "delete stale data cycle task ended unexpectedly" in caplog.messages[0]

    async def test_stop_when_delete_stale_data_cycle_is_not_running(self) -> None:
        user_respond_throttler = UserRespondThrottler(
            response_cooldown=DEFAULT_COOLDOWN
        )
        with pytest.raises(BotThrottlerError):
            await user_respond_throttler.stop_delete_stale_data_cycle()

    async def test_acquire_after_stop_delete_stale_data_cycle(
        self, user_respond_throttler: UserRespondThrottler
    ) -> None:
        await user_respond_throttler.stop_delete_stale_data_cycle()
        with pytest.raises(BotThrottlerError):
            await user_respond_throttler.acquire(FAKE_CHAT_ID)
