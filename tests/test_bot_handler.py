# pyright: reportPrivateUsage=false
import os
import pytest
from unittest.mock import patch, Mock, DEFAULT
import asyncio
from types import TracebackType
from typing import Optional, Any, Self, cast
from collections.abc import Iterable
from contextlib import suppress
import time
from datetime import timedelta
from dataclasses import dataclass
from telegram import Bot, Update
from telegram.error import (
    TelegramError,
    NetworkError,
    Forbidden,
    BadRequest,
    TimedOut,
    RetryAfter,
)
from tests.mock_class.mock_bot_respond_handler import FakeBotRespondHandler
from tests.mock_class.mock_bot_state_handler import FakeBotStateHandler
from tests.mock_class.mock_bot_respond_throttler import (
    FakeGlobalRespondThrottler,
    FakeUserRespondThrottler,
)
from src.bot.bot_handler import BotHandler
from src.models.contexts import BotUpdateContext
from src.models.enums import Commands
from src import exceptions

os.environ["PTB_TIMEDELTA"] = "1"  # avoid PTBDeprecationWarning

FAKE_BOT_TOKEN = "fake_bot_token"
FAKE_CURRENT_OFFSET = 0
FAKE_CHAT_ID = 1
FAKE_UPDATE = Update(update_id=1)
FAKE_UPDATE_CONTEXT = BotUpdateContext(
    chat_id=FAKE_CHAT_ID, command=Commands.START, command_value="karawang"
)
FAKE_RESPOND_MESSAGE = "fake respond message"
FAKE_RETRY_ATTEMPT = 5


class StopLoop(Exception):
    """Raised to stop an infinite loop in this test module"""

    pass


async def cancel_task(task: asyncio.Task[Any]) -> None:
    """
    Cancel a task then waits until the cancellation
    is finished
    """
    try:
        task.cancel()
    finally:
        with suppress(BaseException):
            await task


class FakeTelegramBot:
    async def __aenter__(self) -> Self:
        """Mock the bot context manager"""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[Exception]],
        exc: Optional[Exception],
        tzb: Optional[TracebackType],
    ) -> None:
        """Mock the bot context manager"""
        pass

    async def get_updates(self, offset: Any, timeout: Any) -> tuple[Update, ...]:
        """
        if offset=0, return an empty tuple,
        else return a tuple with 1 fake Update objects
        """
        await asyncio.sleep(0)  # yield control
        if offset == 0:
            return ()
        return (FAKE_UPDATE,)

    async def send_message(
        self, chat_id: int, message: str, parse_mode: str, read_timeout: float
    ) -> None:
        pass


@dataclass(frozen=True)
class BotHandlerContext:
    """Used to holds BotHandler object with its fake dependencies"""

    bot_handler: BotHandler
    fake_bot: Bot
    fake_respond_handler: FakeBotRespondHandler
    fake_bot_state: FakeBotStateHandler
    fake_global_throttler: FakeGlobalRespondThrottler
    fake_user_throttler: FakeUserRespondThrottler


@pytest.fixture
def bot_handler_context() -> Iterable[BotHandlerContext]:
    respond_handler = FakeBotRespondHandler()
    bot_state = FakeBotStateHandler()
    global_throttler = FakeGlobalRespondThrottler()
    user_throttler = FakeUserRespondThrottler()
    fake_bot = FakeTelegramBot()
    bot_handler = BotHandler(
        respond_handler=respond_handler,
        bot_state=bot_state,
        global_throttler=global_throttler,
        user_throttler=user_throttler,
    )
    with patch("src.bot.bot_handler.Bot", return_value=fake_bot):
        yield BotHandlerContext(
            bot_handler=bot_handler,
            fake_bot=cast(Bot, fake_bot),  # cast it as Bot to satisfy type checker
            fake_respond_handler=respond_handler,
            fake_bot_state=bot_state,
            fake_global_throttler=global_throttler,
            fake_user_throttler=user_throttler,
        )


class TestRunBot:
    async def test_bot_is_running_state_flipped(
        self, bot_handler_context: BotHandlerContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(20)  # level: INFO
        bot_handler = bot_handler_context.bot_handler
        # assert the state is not True yet
        assert not bot_handler._bot_is_running
        task = asyncio.create_task(bot_handler.run_bot(bot_token=FAKE_BOT_TOKEN))
        await asyncio.sleep(0)
        assert bot_handler._bot_is_running
        assert "Bot started" in caplog.messages
        bot_handler.stop_bot()

        await cancel_task(task)

    async def test_run_the_bot_twice(
        self, bot_handler_context: BotHandlerContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(30)  # level: WARNING
        bot_handler = bot_handler_context.bot_handler
        task = asyncio.create_task(bot_handler.run_bot(bot_token=FAKE_BOT_TOKEN))
        await asyncio.sleep(0)
        # making sure the bot is running first
        assert bot_handler._bot_is_running
        await bot_handler.run_bot(bot_token=FAKE_BOT_TOKEN)
        assert "Bot is already running, no need to run again" in caplog.messages

        await cancel_task(task)

    async def test_called_methods_and_args(
        self,
        bot_handler_context: BotHandlerContext,
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with (
            patch.object(
                bot_handler, "_start_polling_loop", side_effect=StopLoop()
            ) as mock_start_polling_loop,
            patch.object(bot_handler, "_stop_throttlers") as mock_stop_throttlers,
        ):
            with suppress(StopLoop):
                await bot_handler.run_bot(bot_token=FAKE_BOT_TOKEN)
        assert (
            not bot_handler._bot_is_running
        )  # run_bot() switch the state when it exits
        mock_start_polling_loop.assert_awaited_once_with(
            FAKE_BOT_TOKEN,
            1,  # 1 is based on fake get_offset
        )
        mock_stop_throttlers.assert_awaited_once()
        bot_handler_context.fake_bot_state.assert_called_once_with(
            bot_handler.bot_state.get_offset, [FAKE_BOT_TOKEN]
        )
        bot_handler_context.fake_global_throttler.assert_called_once(
            bot_handler.global_throttler.start_reset_timer
        )
        bot_handler_context.fake_user_throttler.assert_called_once_with(
            bot_handler.user_throttler.start_delete_stale_data_cycle
        )

    @pytest.mark.parametrize(
        "network_exception",
        [
            NetworkError("fake network error"),
            BadRequest("fake bad request"),
            TimedOut("fake timed out"),
        ],
    )
    async def test_when_networks_error_raised(
        self,
        bot_handler_context: BotHandlerContext,
        caplog: pytest.LogCaptureFixture,
        network_exception: NetworkError,
    ) -> None:
        """
        Test that run_bot() tries to rerun _start_long_polling()
        when it raised NetworkError
        """
        caplog.set_level(30)  # level: WARNING
        bot_handler = bot_handler_context.bot_handler
        bot_handler.INITIAL_BACKOFF_DELAY = 0
        with patch.object(
            bot_handler,
            "_start_polling_loop",
            side_effect=[network_exception, StopLoop()],
        ):
            with suppress(StopLoop):
                await bot_handler.run_bot(bot_token=FAKE_BOT_TOKEN)
        assert (
            f"Network error occurred: {repr(network_exception)}, retrying in"
            in caplog.messages[0]
        )

    class TestExponentialBackoffLogic:
        async def test_exponential_backoff_values(
            self,
            bot_handler_context: BotHandlerContext,
            caplog: pytest.LogCaptureFixture,
        ) -> None:
            """Test the delays when exponential backoff retry is triggered"""
            caplog.set_level(30)  # level: WARNING
            bot_handler = bot_handler_context.bot_handler
            bot_handler.INITIAL_BACKOFF_DELAY = 0.01
            with patch.object(
                bot_handler,
                "_start_polling_loop",
                side_effect=[
                    NetworkError("fake network error"),
                    NetworkError("fake network error"),
                    NetworkError("fake network error"),
                    StopLoop(),
                ],
            ):
                with suppress(StopLoop):
                    await bot_handler.run_bot(FAKE_BOT_TOKEN)
            assert "retrying in 0.01" in caplog.messages[0]
            assert "retrying in 0.02" in caplog.messages[1]
            assert "retrying in 0.04" in caplog.messages[2]

        async def test_max_exponential_backoff_value(
            self,
            bot_handler_context: BotHandlerContext,
            caplog: pytest.LogCaptureFixture,
        ) -> None:
            """
            Test that the backoff delays does not exceed more than the
            BotHandler.MAX_BACKOFF_DELAY
            """
            caplog.set_level(30)  # level: WARNING
            bot_handler = bot_handler_context.bot_handler
            bot_handler.INITIAL_BACKOFF_DELAY = 0.02
            bot_handler.MAX_BACKOFF_DELAY = 0.03
            with patch.object(
                bot_handler,
                "_start_polling_loop",
                side_effect=[
                    NetworkError("fake network error"),
                    NetworkError("fake network error"),
                    NetworkError("fake network error"),
                    StopLoop(),
                ],
            ):
                with suppress(StopLoop):
                    await bot_handler.run_bot(FAKE_BOT_TOKEN)
            assert "retrying in 0.02" in caplog.messages[0]
            assert "retrying in 0.03" in caplog.messages[1]
            assert "retrying in 0.03" in caplog.messages[2]

        async def test_backoff_delay_reset_to_inital_backoff_value(
            self,
            bot_handler_context: BotHandlerContext,
            caplog: pytest.LogCaptureFixture,
        ) -> None:
            """
            Test that the backoff delay goes back to the
            initial value (BotHandler.INITIAL_BACKOFF_DELAY)
            when no NetworkError occured after
            a prolonged time (connection was stable)
            """
            caplog.set_level(30)  # level: WARNING
            bot_handler = bot_handler_context.bot_handler
            bot_handler.INITIAL_BACKOFF_DELAY = 0.02
            bot_handler.RESET_BACKOFF_DELAY_AFTER = 0.05
            call_count = 0

            async def _fake_polling_loop(*args: Any, **kwargs: Any) -> None:
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise NetworkError("fake network error")
                if call_count == 3:
                    # simulate a stable polling run,
                    # which mean no NetworkError occured for a prolonged time
                    await asyncio.sleep(
                        0.06  # slightly above the RESET_BACKOFF_DELAY_AFTER
                    )
                    raise NetworkError("fake network error")
                raise StopLoop()

            with patch.object(
                bot_handler,
                "_start_polling_loop",
                side_effect=_fake_polling_loop,
            ):
                with suppress(StopLoop):
                    await bot_handler.run_bot(FAKE_BOT_TOKEN)
            assert "retrying in 0.02" in caplog.messages[0]
            assert "retrying in 0.04" in caplog.messages[1]
            assert "retrying in 0.02" in caplog.messages[2]


class TestStopBot:
    def test_bot_state_flipped(self, bot_handler_context: BotHandlerContext) -> None:
        bot_handler = bot_handler_context.bot_handler
        # first, set the state of bot_handler._bot_is_running to True
        # because making it True through run_bot() requires
        # the run_bot() to be called as a Task
        bot_handler._bot_is_running = True
        bot_handler.stop_bot()
        assert not bot_handler._bot_is_running

    def test_stop_bot_twice(
        self, bot_handler_context: BotHandlerContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(30)  # level: WARNING
        bot_handler = bot_handler_context.bot_handler
        bot_handler._bot_is_running = True
        bot_handler.stop_bot()
        bot_handler.stop_bot()  # second call, should logs a warning
        assert not bot_handler._bot_is_running
        assert "no need to stop" in caplog.messages[0]

    async def test_run_bot_task_stopped(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        """
        Test when run_bot() which contains a loop inside it is stopped
        by stop_bot() when run_bot() runs as a Task
        """
        bot_handler = bot_handler_context.bot_handler
        task = asyncio.create_task(bot_handler.run_bot(FAKE_BOT_TOKEN))
        await asyncio.sleep(0)

        assert bot_handler._bot_is_running
        bot_handler.stop_bot()
        assert not bot_handler._bot_is_running

        await task  # wait for full shutdown
        await cancel_task(task)


class TestStopThrottlers:
    class FakeError(Exception):
        """Fake error for testing purpose"""

        pass

    async def test_throttlers_stopped(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        await bot_handler._stop_throttlers()
        bot_handler_context.fake_global_throttler.assert_called_once(
            bot_handler.global_throttler.stop_reset_timer
        )

    async def test_when_stop_reset_timer_raised_error(
        self,
        bot_handler_context: BotHandlerContext,
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.object(
            bot_handler.global_throttler,
            "stop_reset_timer",
            side_effect=self.FakeError("fake error"),
        ):
            with pytest.raises(ExceptionGroup) as exc_info:
                await bot_handler._stop_throttlers()
        # assert that only one exception was raised as ExceptionGroup
        assert len(exc_info.value.exceptions) == 1
        assert isinstance(exc_info.value.exceptions[0], self.FakeError)
        assert exc_info.value.message == "Errors while stopping the throttlers"
        assert exc_info.value.exceptions[0].args[0] == "fake error"

    async def test_when_stop_delete_stale_data_cycle_raised_error(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.object(
            bot_handler.user_throttler,
            "stop_delete_stale_data_cycle",
            side_effect=self.FakeError("fake error"),
        ):
            with pytest.raises(ExceptionGroup) as exc_info:
                await bot_handler._stop_throttlers()
        # assert that only one exception was raised as ExceptionGroup
        assert len(exc_info.value.exceptions) == 1
        assert isinstance(exc_info.value.exceptions[0], self.FakeError)
        assert exc_info.value.message == "Errors while stopping the throttlers"
        assert exc_info.value.exceptions[0].args[0] == "fake error"

    async def test_when_both_stop_method_of_throttlers_raised_error(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        fake_error_1 = self.FakeError("fake error stop_reset_timer")
        fake_error_2 = self.FakeError("fake error stop_delete_stale_data_cycle")
        with (
            patch.object(
                bot_handler.global_throttler,
                "stop_reset_timer",
                side_effect=fake_error_1,
            ),
            patch.object(
                bot_handler.user_throttler,
                "stop_delete_stale_data_cycle",
                side_effect=fake_error_2,
            ),
        ):
            with pytest.raises(ExceptionGroup) as exc_info:
                await bot_handler._stop_throttlers()
        # assert that two exceptions was raised as ExceptionGroup
        assert len(exc_info.value.exceptions) == 2
        assert exc_info.value.message == "Errors while stopping the throttlers"
        assert fake_error_1 in exc_info.value.exceptions
        assert fake_error_2 in exc_info.value.exceptions


class TestStartPollingLoop:
    pass


class TestDrainTasks:
    pass


class TestPollOnce:
    async def test_called_methods_and_args_when_updates_is_empty(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.object(
            bot_handler_context.fake_bot,
            "get_updates",
            wraps=bot_handler_context.fake_bot.get_updates,
        ) as mock_get_updates:
            await bot_handler._poll_once(
                bot=bot_handler_context.fake_bot, current_offset=FAKE_CURRENT_OFFSET
            )
        mock_get_updates.assert_awaited_once_with(
            offset=FAKE_CURRENT_OFFSET, timeout=bot_handler.POLLING_TIMEOUT
        )

    async def test_called_methods_and_args_when_updates_is_not_empty(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with (
            patch.object(
                bot_handler_context.fake_bot,
                "get_updates",
                wraps=bot_handler_context.fake_bot.get_updates,
            ) as mock_get_updates,
            patch.object(
                bot_handler, "_create_respond_to_update_task"
            ) as mock_create_update_task,
        ):
            # set the offset to 1 so fake_bot.get_updates() return non-empty tuple
            await bot_handler._poll_once(
                bot=bot_handler_context.fake_bot, current_offset=1
            )
        mock_get_updates.assert_awaited_once_with(
            offset=1, timeout=bot_handler.POLLING_TIMEOUT
        )
        mock_create_update_task.assert_called_once_with(
            bot_handler_context.fake_bot, FAKE_UPDATE
        )

    async def test_returned_offset_when_updates_is_empty(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        """
        Should return the same offset value with the passed
        'current_offset' arg
        """
        bot_handler = bot_handler_context.bot_handler
        result = await bot_handler._poll_once(
            bot=bot_handler_context.fake_bot, current_offset=FAKE_CURRENT_OFFSET
        )
        assert result == FAKE_CURRENT_OFFSET

    @pytest.mark.parametrize(
        "fake_updates, should_return",
        [
            ((Update(update_id=1),), 2),
            ((Update(update_id=5),), 6),
            # simulate when get_updates() return more than one Update
            # it should return the last Update.update_id plus 1
            ((Update(update_id=1), Update(update_id=2)), 3),
        ],
    )
    async def test_returned_offset_when_updates_is_not_empty(
        self,
        bot_handler_context: BotHandlerContext,
        fake_updates: tuple[Update, ...],
        should_return: int,
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.object(
            bot_handler_context.fake_bot, "get_updates", return_value=fake_updates
        ):
            result = await bot_handler._poll_once(
                bot=bot_handler_context.fake_bot, current_offset=FAKE_CURRENT_OFFSET
            )
        assert result == should_return


class TestCreateRespondToUpdateTask:
    async def test_task_created(self, bot_handler_context: BotHandlerContext) -> None:
        bot_handler = bot_handler_context.bot_handler
        assert not bot_handler._active_tasks  # assert no active_task yet
        bot_handler._create_respond_to_update_task(
            bot=bot_handler_context.fake_bot, update=FAKE_UPDATE
        )
        await asyncio.sleep(0)
        assert len(bot_handler._active_tasks) == 1
        assert (
            list(bot_handler._active_tasks)[0].get_name()
            == f"respond-for-{FAKE_UPDATE.update_id}"
        )

    async def test_called_methods_and_args_when_effective_chat_id_is_not_none(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        fake_id = 1
        fake_update = Mock()
        fake_update.effective_chat.id = fake_id
        with (
            patch.object(bot_handler, "_respond_to_update") as mock_respond_method,
            patch.object(
                bot_handler, "_handle_task_completion"
            ) as mock_callback_method,
        ):
            bot_handler._create_respond_to_update_task(
                bot=bot_handler_context.fake_bot, update=fake_update
            )
            await asyncio.sleep(0)
        mock_respond_method.assert_called_once_with(
            bot_handler_context.fake_bot, fake_update
        )
        mock_callback_method.assert_called_once_with(
            bot_handler_context.fake_bot, fake_id
        )

    async def test_called_methods_and_args_when_effective_chat_id_is_none(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        fake_update = Mock()
        fake_update.effective_chat = None
        with (
            patch.object(bot_handler, "_respond_to_update") as mock_respond_method,
            patch.object(
                bot_handler, "_handle_task_completion"
            ) as mock_callback_method,
        ):
            bot_handler._create_respond_to_update_task(
                bot=bot_handler_context.fake_bot, update=fake_update
            )
            await asyncio.sleep(0)
        mock_respond_method.assert_called_once_with(
            bot_handler_context.fake_bot, fake_update
        )
        mock_callback_method.assert_called_once_with(bot_handler_context.fake_bot, None)


class TestRespondToUpdate:
    async def test_called_method_and_args(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.multiple(
            bot_handler, _parse_update=DEFAULT, _send_message_with_retry=DEFAULT
        ) as mock:
            mock["_parse_update"].return_value = FAKE_UPDATE_CONTEXT
            await bot_handler._respond_to_update(
                bot=bot_handler_context.fake_bot, update=FAKE_UPDATE
            )
        mock["_parse_update"].assert_called_once_with(FAKE_UPDATE)
        bot_handler_context.fake_respond_handler.assert_called_once_with(
            bot_handler.respond_handler.parse_command,
            [
                FAKE_CHAT_ID,
                FAKE_UPDATE_CONTEXT.command,
                FAKE_UPDATE_CONTEXT.command_value,
            ],
        )
        mock["_send_message_with_retry"].assert_awaited_once_with(
            bot_handler_context.fake_bot,
            FAKE_CHAT_ID,
            FAKE_RESPOND_MESSAGE,  # based on tests/mock_class/mock_bot_respond_handler.py
        )

    async def test_when_parse_update_return_none(
        self, bot_handler_context: BotHandlerContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(20)  # level: INFO
        bot_handler = bot_handler_context.bot_handler
        with patch.object(
            bot_handler, "_parse_update", return_value=None
        ) as mock_method:
            await bot_handler._respond_to_update(
                bot=bot_handler_context.fake_bot, update=FAKE_UPDATE
            )
        mock_method.assert_called_once_with(FAKE_UPDATE)
        assert "Skip responding to non Message context" in caplog.messages

    async def test_concurrency_is_bounded(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        total_tasks = bot_handler.MAX_CONCURRENT_TASKS + 5
        in_flight = 0
        peak = 0

        async def _tracked_send(*args: Any, **kwargs: Any) -> None:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                await asyncio.sleep(0.05)
            finally:
                in_flight -= 1

        with (
            patch.object(
                bot_handler, "_send_message_with_retry", side_effect=_tracked_send
            ) as send_mock,
            patch.object(
                bot_handler, "_parse_update", return_value=FAKE_UPDATE_CONTEXT
            ),
        ):
            await asyncio.gather(
                *(
                    bot_handler._respond_to_update(
                        bot=bot_handler_context.fake_bot, update=FAKE_UPDATE
                    )
                    for _ in range(total_tasks)
                )
            )

        assert peak == bot_handler.MAX_CONCURRENT_TASKS
        assert send_mock.call_count == total_tasks


class TestCreateSendBotErrorMessageTask:
    async def test_task_created(self, bot_handler_context: BotHandlerContext) -> None:
        bot_handler = bot_handler_context.bot_handler
        assert not bot_handler._active_tasks  # assert no active_task yet
        bot_handler._create_send_bot_error_message_task(
            bot=bot_handler_context.fake_bot,
            chat_id=FAKE_CHAT_ID,
            err_message="fake err message",
        )
        await asyncio.sleep(0)
        assert len(bot_handler._active_tasks) == 1
        assert (
            list(bot_handler._active_tasks)[0].get_name()
            == f"Error-Message-{FAKE_CHAT_ID}"
        )

    async def test_called_methods_and_args(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.multiple(
            bot_handler, _send_error_message=DEFAULT, _handle_task_completion=DEFAULT
        ) as mock_methods:
            bot_handler._create_send_bot_error_message_task(
                bot=bot_handler_context.fake_bot,
                chat_id=FAKE_CHAT_ID,
                err_message="fake err message",
            )
        mock_methods["_send_error_message"].assert_called_once_with(
            bot_handler_context.fake_bot,
            FAKE_CHAT_ID,
            "fake err message",
        )
        mock_methods["_handle_task_completion"].assert_called_once_with(
            bot_handler_context.fake_bot, FAKE_CHAT_ID
        )


async def test_send_error_message_called_methods_and_args(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    with patch.object(bot_handler, "_send_message_with_retry") as mock_method:
        await bot_handler._send_error_message(
            bot=bot_handler_context.fake_bot,
            chat_id=FAKE_CHAT_ID,
            err_message="fake err message",
        )
    mock_method.assert_awaited_once_with(
        bot_handler_context.fake_bot, FAKE_CHAT_ID, "fake err message"
    )


async def test_send_error_message_concurrency_is_bounded(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    total_tasks = bot_handler.MAX_CONCURRENT_TASKS + 5
    in_flight = 0
    peak = 0

    async def _tracked_send(*args: Any, **kwargs: Any) -> None:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        try:
            await asyncio.sleep(0.05)
        finally:
            in_flight -= 1

    with (
        patch.object(
            bot_handler, "_send_message_with_retry", side_effect=_tracked_send
        ) as send_mock,
    ):
        await asyncio.gather(
            *(
                bot_handler._send_error_message(
                    bot=bot_handler_context.fake_bot,
                    chat_id=FAKE_CHAT_ID,
                    err_message="fake err message",
                )
                for _ in range(total_tasks)
            )
        )

    assert peak == bot_handler.MAX_CONCURRENT_TASKS
    assert send_mock.call_count == total_tasks


class TestSendMessageWithRetry:
    async def test_successful_first_attempt_send_message(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        bot_handler.SEND_MESSAGE_RETRY_ATTEMPT = FAKE_RETRY_ATTEMPT
        with patch.object(bot_handler_context.fake_bot, "send_message") as mock_method:
            await bot_handler._send_message_with_retry(
                bot=bot_handler_context.fake_bot,
                chat_id=FAKE_CHAT_ID,
                message=FAKE_RESPOND_MESSAGE,
            )
        bot_handler_context.fake_global_throttler.assert_called_once(
            bot_handler.global_throttler.acquire
        )
        bot_handler_context.fake_user_throttler.assert_called_once_with(
            bot_handler.user_throttler.acquire, [FAKE_CHAT_ID]
        )
        mock_method.assert_awaited_once_with(
            FAKE_CHAT_ID,
            FAKE_RESPOND_MESSAGE,
            parse_mode="HTML",
            read_timeout=bot_handler.SEND_MESSAGE_TIMEOUT,
        )

    @pytest.mark.parametrize(
        "raised_error",
        [TimedOut("fake timed out"), RetryAfter(timedelta(milliseconds=1))],
    )
    async def test_failed_first_attempt_then_successful_second_attempt_send_message(
        self,
        bot_handler_context: BotHandlerContext,
        caplog: pytest.LogCaptureFixture,
        raised_error: TelegramError,
    ) -> None:
        """
        Test that the retry mechanism is triggered when the first attempt
        of send_message() failed
        """
        caplog.set_level(10)
        bot_handler = bot_handler_context.bot_handler
        bot_handler.SEND_MESSAGE_RETRY_ATTEMPT = FAKE_RETRY_ATTEMPT
        bot_handler.SEND_MESSAGE_RETRY_DELAY = 0
        with (
            patch.object(
                bot_handler_context.fake_bot,
                "send_message",
                side_effect=[raised_error, None],
            ) as mock_send_message_method,
            patch.object(
                bot_handler.user_throttler, "acquire"
            ) as mock_user_acquire_method,
            patch.object(
                bot_handler.global_throttler, "acquire"
            ) as mock_global_acquire_method,
        ):
            await bot_handler._send_message_with_retry(
                bot=bot_handler_context.fake_bot,
                chat_id=FAKE_CHAT_ID,
                message=FAKE_RESPOND_MESSAGE,
            )
        assert mock_send_message_method.call_count == 2
        assert mock_user_acquire_method.call_count == 2
        assert mock_global_acquire_method.call_count == 2
        if isinstance(raised_error, TimedOut):
            assert "send_message timed out" in caplog.messages[0]
        elif isinstance(raised_error, RetryAfter):
            assert "rate limited" in caplog.messages[0]

    async def test_retry_delay_when_send_message_timed_out(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        """
        Test that there is actual delays when the retry mechanism
        was triggered due to TimedOut error
        """
        bot_handler = bot_handler_context.bot_handler
        delay = 0.2
        bot_handler.SEND_MESSAGE_RETRY_DELAY = delay
        bot_handler.SEND_MESSAGE_RETRY_ATTEMPT = FAKE_RETRY_ATTEMPT
        before = time.monotonic()
        with patch.object(
            bot_handler_context.fake_bot,
            "send_message",
            side_effect=[TimedOut(), TimedOut(), None],
        ) as mock_method:
            await bot_handler._send_message_with_retry(
                bot=bot_handler_context.fake_bot,
                chat_id=FAKE_CHAT_ID,
                message=FAKE_RESPOND_MESSAGE,
            )
        # the total delay should be 0.4 since the delay per attempt is 0.2
        # and there are 2 retry attempts in this test case
        assert (time.monotonic() - before) == pytest.approx(0.4, rel=0.01)
        assert mock_method.call_count == 3

    async def test_retry_delay_when_rate_limited(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        """
        Test that there is actual delay before retry attempt
        when the bot gets rate_limited
        and RetryAfter was raised in send_message()
        """
        bot_handler = bot_handler_context.bot_handler
        bot_handler.SEND_MESSAGE_RETRY_ATTEMPT = FAKE_RETRY_ATTEMPT
        fake_retry_after = RetryAfter(
            timedelta(milliseconds=200)  # equal to 0.2 second
        )
        before = time.monotonic()
        with patch.object(
            bot_handler_context.fake_bot,
            "send_message",
            side_effect=[fake_retry_after, None],
        ) as mock_method:
            await bot_handler._send_message_with_retry(
                bot=bot_handler_context.fake_bot,
                chat_id=FAKE_CHAT_ID,
                message=FAKE_RESPOND_MESSAGE,
            )
        assert (time.monotonic() - before) == pytest.approx(0.2, rel=0.01)
        assert mock_method.call_count == 2

    @pytest.mark.parametrize(
        "raised_error",
        [TimedOut("fake timed out"), RetryAfter(timedelta(milliseconds=1))],
    )
    async def test_when_retry_attempt_exhausted(
        self, bot_handler_context: BotHandlerContext, raised_error: TelegramError
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        bot_handler.SEND_MESSAGE_RETRY_DELAY = 0
        bot_handler.SEND_MESSAGE_RETRY_ATTEMPT = FAKE_RETRY_ATTEMPT
        with patch.object(
            bot_handler_context.fake_bot, "send_message", side_effect=raised_error
        ) as mock_method:
            with pytest.raises(exceptions.SendMessageRetryExhaustedError) as exc_info:
                await bot_handler._send_message_with_retry(
                    bot=bot_handler_context.fake_bot,
                    chat_id=FAKE_CHAT_ID,
                    message=FAKE_RESPOND_MESSAGE,
                )
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.retry_attempt == FAKE_RETRY_ATTEMPT
        assert exc_info.value.dropped_message == FAKE_RESPOND_MESSAGE
        # assert actual call_count of send_message()
        assert mock_method.call_count == bot_handler.SEND_MESSAGE_RETRY_ATTEMPT

    @pytest.mark.parametrize(
        "raised_error", [BadRequest("fake bad request"), Forbidden("fake forbidden")]
    )
    async def then_when_non_retryable_error_occured(
        self, bot_handler_context: BotHandlerContext, raised_error: TelegramError
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        with patch.object(
            bot_handler_context.fake_bot, "send_message", side_effect=raised_error
        ) as mock_method:
            with pytest.raises(type(raised_error)):
                await bot_handler._send_message_with_retry(
                    bot=bot_handler_context.fake_bot,
                    chat_id=FAKE_CHAT_ID,
                    message=FAKE_RESPOND_MESSAGE,
                )
        mock_method.assert_awaited_once_with(
            FAKE_CHAT_ID,
            FAKE_RESPOND_MESSAGE,
            parse_mode="HTML",
            read_timeout=bot_handler.SEND_MESSAGE_TIMEOUT,
        )


class TestHandleTaskCompletion:
    class FakeException(Exception):
        """Raised as fake exception for testing purpose"""

    class FakeTaskFactory:
        """
        Used to test task callback behaviour of
        BotHandler._handle_task_completion()
        """

        def __init__(
            self, bot_handler_context: BotHandlerContext, exec: Exception | None
        ) -> None:
            self.bot_handler_context = bot_handler_context
            self.exec = exec

        def create_successful_task(self) -> asyncio.Task[None]:
            """Create a fake task that sleeps for 0 second then return None"""

            async def _successful_task() -> None:
                await asyncio.sleep(0)

            task = asyncio.create_task(_successful_task())
            task.add_done_callback(
                self.bot_handler_context.bot_handler._handle_task_completion(
                    bot=self.bot_handler_context.fake_bot,
                    chat_id=FAKE_CHAT_ID,
                )
            )
            return task

        def create_error_task(
            self, remove_chat_id_in_callback: bool = False
        ) -> asyncio.Task[None]:
            """Create a fake task that sleeps for 0 second then raise an error"""
            chat_id = FAKE_CHAT_ID
            if remove_chat_id_in_callback:
                chat_id = None

            async def _error_task() -> None:
                assert self.exec is not None, (
                    "valid indirect param exception is needed to create an error task"
                )
                await asyncio.sleep(0)
                raise self.exec

            task = asyncio.create_task(_error_task())
            task.add_done_callback(
                self.bot_handler_context.bot_handler._handle_task_completion(
                    bot=self.bot_handler_context.fake_bot,
                    chat_id=chat_id,
                )
            )
            self.bot_handler_context.bot_handler._active_tasks.add(task)
            return task

    @pytest.fixture()
    def exec(self, request: pytest.FixtureRequest) -> Exception | None:
        try:
            return request.param
        except AttributeError:
            return None

    @pytest.fixture(autouse=True)
    def task_factory(
        self, exec: Exception | None, bot_handler_context: BotHandlerContext
    ) -> FakeTaskFactory:
        return self.FakeTaskFactory(bot_handler_context, exec)

    async def test_active_tasks_discarded_when_no_error_was_raised(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        """
        Test that new task was added to bot_handeler.active_tasks
        then discarded when it finished without any error
        """
        bot_handler = bot_handler_context.bot_handler
        total_task_to_create = 5

        async def _sleep(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(0)

        assert len(bot_handler._active_tasks) == 0, (
            "should be zero since no task was added yet"
        )
        with patch.object(
            bot_handler, "_respond_to_update", side_effect=_sleep
        ) as mock_respond_method:
            for _ in range(total_task_to_create):
                bot_handler._create_respond_to_update_task(
                    bot=bot_handler_context.fake_bot, update=FAKE_UPDATE
                )
            assert len(bot_handler._active_tasks) == total_task_to_create, (
                f"should be {total_task_to_create} because _create_respond_to_update_task()"
                f" was called {total_task_to_create} times"
            )
            await asyncio.sleep(0.01)  # let all the created tasks run
        assert len(bot_handler._active_tasks) == 0, (
            "should be 0 after all tasks is done"
        )
        assert mock_respond_method.call_count == 5
        # cancel tasks if any
        for task in bot_handler._active_tasks:
            await cancel_task(task)

    async def test_active_tasks_discarded_when_error_was_raised(
        self, bot_handler_context: BotHandlerContext
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        total_task_to_create = 5

        async def _raise(*args: Any, **kwargs: Any) -> None:
            await asyncio.sleep(0)
            raise self.FakeException()

        assert len(bot_handler._active_tasks) == 0, (
            "should be zero since no task was added yet"
        )
        with patch.object(
            bot_handler, "_respond_to_update", side_effect=_raise
        ) as mock_respond_method:
            for _ in range(total_task_to_create):
                bot_handler._create_respond_to_update_task(
                    bot=bot_handler_context.fake_bot, update=FAKE_UPDATE
                )
            assert len(bot_handler._active_tasks) == total_task_to_create, (
                f"should be {total_task_to_create} because _create_respond_to_update_task()"
                f" was called {total_task_to_create} times"
            )
            await asyncio.sleep(0.01)  # let all the created tasks run
        assert len(bot_handler._active_tasks) == 0, (
            "should be 0 after all tasks is done"
        )
        assert mock_respond_method.call_count == 5
        # cancel tasks if any
        for task in bot_handler._active_tasks:
            await cancel_task(task)

    @pytest.mark.parametrize("exec", [None], indirect=True)
    async def test_callback_when_no_error_was_raised(
        self, task_factory: FakeTaskFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        task = task_factory.create_successful_task()
        await task
        assert "finished successfully" in caplog.messages[0]

        await cancel_task(task)

    @pytest.mark.parametrize(
        "exec",
        [
            exceptions.SendMessageRetryExhaustedError(
                chat_id=FAKE_CHAT_ID,
                retry_attempt=FAKE_RETRY_ATTEMPT,
                dropped_message=FAKE_RESPOND_MESSAGE,
            )
        ],
        indirect=True,
    )
    async def test_callback_when_send_message_retry_exhausted_error_raised(
        self, task_factory: FakeTaskFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        task = task_factory.create_error_task()
        with pytest.raises(exceptions.SendMessageRetryExhaustedError) as exc_info:
            await task
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.retry_attempt == FAKE_RETRY_ATTEMPT
        assert exc_info.value.dropped_message == FAKE_RESPOND_MESSAGE
        assert "retry attempt reached" in caplog.messages[0]
        assert f"dropped_message: {FAKE_RESPOND_MESSAGE}" in caplog.messages[0]
        assert "finished with error" in caplog.messages[1]

        await cancel_task(task)

    @pytest.mark.parametrize(
        "exec",
        [
            exceptions.EmptyMessageTextError(FAKE_CHAT_ID),
            exceptions.NoForecastResultError(FAKE_CHAT_ID, FAKE_RESPOND_MESSAGE),
            exceptions.InvalidCommandError(FAKE_CHAT_ID, "fake command"),
            exceptions.NotCommandTypeError(FAKE_CHAT_ID, "fake text"),
            exceptions.DataIntegrityError(FAKE_CHAT_ID, "fake message"),
        ],
        indirect=True,
    )
    async def test_callback_when_bot_handler_error_raised_where_chat_id_is_not_none(
        self,
        bot_handler_context: BotHandlerContext,
        task_factory: FakeTaskFactory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(10)
        bot_handler = bot_handler_context.bot_handler
        task = task_factory.create_error_task()
        with patch.object(
            bot_handler, "_create_send_bot_error_message_task"
        ) as mock_method:
            assert isinstance(task_factory.exec, exceptions.BotHandlerError), (
                "passed exception should be part of BotHandlerError!"
            )
            with pytest.raises(type(task_factory.exec)) as exc_info:
                await task
        assert exc_info.value.message in caplog.messages[0]
        assert "finished with error" in caplog.messages[1]
        mock_method.assert_called_once_with(
            bot_handler_context.fake_bot,
            FAKE_CHAT_ID,
            task_factory.exec.message,
        )

        await cancel_task(task)

    @pytest.mark.parametrize(
        "exec",
        [
            exceptions.EmptyMessageTextError(FAKE_CHAT_ID),
            exceptions.NoForecastResultError(FAKE_CHAT_ID, FAKE_RESPOND_MESSAGE),
            exceptions.InvalidCommandError(FAKE_CHAT_ID, "fake command"),
            exceptions.NotCommandTypeError(FAKE_CHAT_ID, "fake text"),
            exceptions.DataIntegrityError(FAKE_CHAT_ID, "fake message"),
        ],
        indirect=True,
    )
    async def test_callback_when_bot_handler_error_raised_where_chat_id_is_none(
        self,
        bot_handler_context: BotHandlerContext,
        task_factory: FakeTaskFactory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(10)
        bot_handler = bot_handler_context.bot_handler
        task = task_factory.create_error_task(remove_chat_id_in_callback=True)
        with patch.object(
            bot_handler, "_create_send_bot_error_message_task"
        ) as mock_method:
            assert isinstance(task_factory.exec, exceptions.BotHandlerError), (
                "passed exception should be part of BotHandlerError!"
            )
            with pytest.raises(type(task_factory.exec)) as exc_info:
                await task
        assert exc_info.value.message in caplog.messages[0]
        assert "Skip responding to non Chat context" in caplog.messages[1]
        assert "finished with error" in caplog.messages[2]
        mock_method.assert_not_called()

        await cancel_task(task)

    @pytest.mark.parametrize("exec", [BadRequest("fake bad request")], indirect=True)
    async def test_callback_when_bad_request_error_raised(
        self, task_factory: FakeTaskFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        task = task_factory.create_error_task()
        with pytest.raises(BadRequest):
            await task
        assert "Bad request:" in caplog.messages[0]
        assert "finished with error" in caplog.messages[1]

        await cancel_task(task)

    @pytest.mark.parametrize(
        "exec", [NetworkError("fake network error")], indirect=True
    )
    async def test_callback_when_network_error_raised(
        self, task_factory: FakeTaskFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        task = task_factory.create_error_task()
        with pytest.raises(NetworkError):
            await task
        assert "Network error:" in caplog.messages[0]
        assert "finished with error" in caplog.messages[1]

        await cancel_task(task)

    @pytest.mark.parametrize("exec", [asyncio.CancelledError()], indirect=True)
    async def test_callback_when_cancelled_error_raised(
        self, task_factory: FakeTaskFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        task = task_factory.create_error_task()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert "Task was cancelled" in caplog.messages[0]
        assert "finished with error" in caplog.messages[1]

        await cancel_task(task)

    @pytest.mark.parametrize(
        "exec", [FakeException(), RuntimeError(), AttributeError()], indirect=True
    )
    async def test_callback_when_exception_error_raised(
        self, task_factory: FakeTaskFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        task = task_factory.create_error_task()
        assert isinstance(task_factory.exec, Exception), (
            "passed exception should be part of Exception!"
        )
        with pytest.raises(type(task_factory.exec)):
            await task
        assert f"Unexpected error: {repr(task_factory.exec)}" in caplog.messages[0]
        assert "finished with error" in caplog.messages[1]

        await cancel_task(task)


def test_parse_retry_after_when_passed_arg_is_int_type(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    value = 1
    result = bot_handler._parse_retry_after(value)
    assert isinstance(result, float)
    assert value == 1


@pytest.mark.parametrize(
    "passed_value, expected_return",
    [
        (timedelta(seconds=1), 1),
        (timedelta(seconds=65), 65),
        (timedelta(minutes=30), 1800),
        (timedelta(hours=1), 3600),
    ],
)
def test_parse_retry_after_when_passed_arg_is_timedelta_type(
    bot_handler_context: BotHandlerContext,
    passed_value: timedelta,
    expected_return: float,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    result = bot_handler._parse_retry_after(passed_value)
    assert isinstance(result, float)
    assert result == expected_return


class TestParseUpdate:
    @pytest.fixture
    def fake_update(self) -> Mock:
        mock = Mock()
        mock.message.chat_id = FAKE_CHAT_ID
        return mock

    def test_when_all_is_valid_where_the_splitted_text_length_is_one(
        self, bot_handler_context: BotHandlerContext, fake_update: Mock
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        fake_update.message.text = "/start"
        result = bot_handler._parse_update(update=fake_update)
        assert result is not None
        assert result.chat_id == FAKE_CHAT_ID
        assert result.command == Commands.START
        assert result.command_value is None

    @pytest.mark.parametrize(
        "text, expected_return",
        [
            (
                "/start value_a",
                BotUpdateContext(FAKE_CHAT_ID, Commands.START, "value_a"),
            ),
            (
                "/start value_a value_b",
                BotUpdateContext(FAKE_CHAT_ID, Commands.START, "value_a value_b"),
            ),
            (
                "/help my bini gw",
                BotUpdateContext(FAKE_CHAT_ID, Commands.HELP, "my bini gw"),
            ),
        ],
    )
    def test_when_all_is_valid_where_the_splitted_text_length_is_more_than_one(
        self,
        bot_handler_context: BotHandlerContext,
        fake_update: Mock,
        text: str,
        expected_return: BotUpdateContext,
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        fake_update.message.text = text
        result = bot_handler._parse_update(update=fake_update)
        assert result == expected_return

    def test_when_update_message_is_none(
        self, bot_handler_context: BotHandlerContext, fake_update: Mock
    ) -> None:
        """Test that _parse_update() return None when Update.message is None"""
        bot_handler = bot_handler_context.bot_handler
        fake_update.message = None
        result = bot_handler._parse_update(update=fake_update)
        assert result is None

    def test_when_update_message_text_is_none(
        self, bot_handler_context: BotHandlerContext, fake_update: Mock
    ) -> None:
        """
        Possible to happen in a case where the Update obj contains a Message obj
        where it's not a plain text, for example photo, caption, video, voice, etc
        """
        bot_handler = bot_handler_context.bot_handler
        fake_update.message.text = None
        with pytest.raises(exceptions.EmptyMessageTextError) as exc_info:
            bot_handler._parse_update(update=fake_update)
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.message == "This bot can only proceed plain text"

    @pytest.mark.parametrize("text", ["start", "start value_a", "value_a /start"])
    def test_when_update_message_first_text_is_not_a_command(
        self, bot_handler_context: BotHandlerContext, fake_update: Mock, text: str
    ) -> None:
        """
        Test when user send a plain text where the first text
        does not start with a slash (/), which mean it's not a command
        """
        bot_handler = bot_handler_context.bot_handler
        fake_update.message.text = text
        with pytest.raises(exceptions.NotCommandTypeError) as exc_info:
            bot_handler._parse_update(update=fake_update)
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.text == text.split()[0]
        assert (
            exc_info.value.message
            == "First text have to be a command, started with / (a slash)"
        )

    def test_when_command_text_is_not_valid(
        self, bot_handler_context: BotHandlerContext, fake_update: Mock
    ) -> None:
        bot_handler = bot_handler_context.bot_handler
        invalid_command = "/wkwkwk"
        fake_update.message.text = invalid_command
        # assert first that the fake message text command is invalid
        with suppress(ValueError):
            Commands(invalid_command)
            assert False, (
                f"{invalid_command} is a valid Commands, when its expected to be invalid"
            )
        with pytest.raises(exceptions.InvalidCommandError) as exc_info:
            bot_handler._parse_update(update=fake_update)
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.command == invalid_command
        assert (
            exc_info.value.message
            == f"{invalid_command} is not a known command, type /help to see available commands"
        )


def test_validate_text_is_not_none_when_passed_text_is_not_none(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    result = bot_handler._validate_text_is_not_none(
        text="fake text", chat_id=FAKE_CHAT_ID
    )
    assert result == "fake text"


def test_validate_text_is_not_none_when_passed_text_is_none(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    with pytest.raises(exceptions.EmptyMessageTextError) as exc_info:
        bot_handler._validate_text_is_not_none(text=None, chat_id=FAKE_CHAT_ID)
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.message == "This bot can only proceed plain text"


def test_validate_first_text_is_command_when_first_text_start_with_slash(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    result = bot_handler._validate_first_text_is_command(
        first_text="/fake_command", chat_id=FAKE_CHAT_ID
    )
    assert result == "/fake_command"


def test_validate_first_text_is_command_when_first_text_does_not_start_with_slash(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    with pytest.raises(exceptions.NotCommandTypeError) as exc_info:
        bot_handler._validate_first_text_is_command(
            first_text="fake_command", chat_id=FAKE_CHAT_ID
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.text == "fake_command"
    assert (
        exc_info.value.message
        == "First text have to be a command, started with / (a slash)"
    )


def test_validate_command_is_valid_when_passed_command_is_valid(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    result = bot_handler._validate_command_is_valid(
        command_text="/start", chat_id=FAKE_CHAT_ID
    )
    assert result == Commands.START


def test_validate_command_is_valid_when_passed_command_is_not_valid(
    bot_handler_context: BotHandlerContext,
) -> None:
    bot_handler = bot_handler_context.bot_handler
    invalid_command = "/wkwkwk"
    # assert first that the invalid_command is truly invalid
    with suppress(ValueError):
        Commands(invalid_command)
        assert False, (
            f"{invalid_command} is a valid Commands, when its expected to be invalid"
        )
    with pytest.raises(exceptions.InvalidCommandError) as exc_info:
        bot_handler._validate_command_is_valid(
            command_text=invalid_command, chat_id=FAKE_CHAT_ID
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.command == invalid_command
    assert (
        exc_info.value.message
        == f"{invalid_command} is not a known command, type /help to see available commands"
    )
