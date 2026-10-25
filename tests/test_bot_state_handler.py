# pyright: reportPrivateUsage=false
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.bot.bot_state_handler import BotStateHandler

FAKE_BOT_TOKEN = "fake bot token"
FAKE_OFFSET = 1


@pytest.fixture
def bot_state_handler() -> BotStateHandler:
    fake_offset = Mock(offset=FAKE_OFFSET)
    mock_bot_query = Mock()
    mock_bot_query.get_bot_offset = AsyncMock(return_value=fake_offset)
    mock_bot_query.insert_or_update_bot_offset = AsyncMock()
    return BotStateHandler(mock_bot_query)


@pytest.fixture
def bot_state_handler_none_offset() -> BotStateHandler:
    """In case the query return a row but no offset data."""
    fake_offset = Mock(offset=None)
    mock_bot_query = Mock()
    mock_bot_query.get_bot_offset = AsyncMock(return_value=fake_offset)
    return BotStateHandler(mock_bot_query)


@pytest.fixture
def bot_state_handler_none_row() -> BotStateHandler:
    """In case the query return no row."""
    mock_bot_query = Mock()
    # simulate bot_query.get_bot_offset() return None instead of Row object
    mock_bot_query.get_bot_offset = AsyncMock(return_value=None)
    return BotStateHandler(mock_bot_query)


class TestBotStateHandlerObjectCreation:
    @patch.object(BotStateHandler, "OFFSET_STORE_INTERVAL", new=1)
    def test_when_offset_store_interval_is_more_than_zero(self) -> None:
        obj = BotStateHandler(bot_query=Mock())
        assert isinstance(obj, BotStateHandler)

    @patch.object(BotStateHandler, "OFFSET_STORE_INTERVAL", new=0)
    def test_when_offset_store_interval_is_equal_to_zero(self) -> None:
        with pytest.raises(RuntimeError):
            BotStateHandler(bot_query=Mock())

    @patch.object(BotStateHandler, "OFFSET_STORE_INTERVAL", new=-1)
    def test_when_offset_store_interval_is_less_than_zero(self) -> None:
        with pytest.raises(RuntimeError):
            BotStateHandler(bot_query=Mock())


class TestGetOffset:
    async def test_when_bot_query_return_row_object(
        self,
        bot_state_handler: BotStateHandler,
    ) -> None:
        result = await bot_state_handler.get_offset("fake_token")
        assert result == FAKE_OFFSET

    async def test_when_bot_query_return_row_object_with_none_offset_attr(
        self,
        bot_state_handler_none_offset: BotStateHandler,
    ) -> None:
        """
        Test that get_offset() return None when the bot_query return
        Row object without the offset data.
        """
        result = await bot_state_handler_none_offset.get_offset("fake_token")
        assert result is None

    async def test_when_bot_query_return_none(
        self,
        bot_state_handler_none_row: BotStateHandler,
    ) -> None:
        """
        Test that get_offset() return None when the bot_query return None
        instead of a Row object.
        """
        result = await bot_state_handler_none_row.get_offset("fake_token")
        assert result is None


class TestStoreOffset:
    async def test_when_can_run_return_true(
        self, bot_state_handler: BotStateHandler
    ) -> None:
        # patch bot_state_handler._can_run() return True
        with patch.object(bot_state_handler, "_can_run", return_value=True):
            await bot_state_handler.store_offset(
                bot_token=FAKE_BOT_TOKEN, offset=FAKE_OFFSET
            )
        bot_state_handler.query.insert_or_update_bot_offset.assert_awaited_once_with(  # type: ignore[attr-defined]
            FAKE_BOT_TOKEN, FAKE_OFFSET
        )

    async def test_when_can_run_return_false(
        self, bot_state_handler: BotStateHandler
    ) -> None:
        # patch bot_state_handler._can_run() return False
        with patch.object(bot_state_handler, "_can_run", return_value=False):
            await bot_state_handler.store_offset(
                bot_token=FAKE_BOT_TOKEN, offset=FAKE_OFFSET
            )
        bot_state_handler.query.insert_or_update_bot_offset.assert_not_awaited()  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "can_run_return",
        [True, False],
        ids=["_can_run() return True", "_can_run() return False"],
    )
    async def test_when_force_store_is_true(
        self,
        bot_state_handler: BotStateHandler,
        can_run_return: bool,
    ) -> None:
        """
        Test that bot_query.insert_or_update_bot_offset is called when
        force_store = True, which means it skips
        the 'has enough time passed check' in bot_state_handler._can_run()
        """
        with patch.object(bot_state_handler, "_can_run", return_value=can_run_return):
            await bot_state_handler.store_offset(
                bot_token=FAKE_BOT_TOKEN, offset=FAKE_OFFSET, force_store=True
            )
        bot_state_handler.query.insert_or_update_bot_offset.assert_awaited_once_with(  # type: ignore[attr-defined]
            FAKE_BOT_TOKEN, FAKE_OFFSET
        )


class TestCanRun:
    def test_return_when_last_offset_store_is_none(
        self,
        bot_state_handler: BotStateHandler,
    ) -> None:
        """
        Test that bot_state_handler._can_run() return True,
        when self._last_offset_store is None.
        """
        # explicitly making the attr None
        bot_state_handler._next_offset_store = None
        result = bot_state_handler._can_run(Mock())
        assert result

    async def test_return_when_called_before_next_offset_store(
        self,
        bot_state_handler: BotStateHandler,
    ) -> None:
        """
        Test that bot_state_handler._can_run() return False
        when _can_run() was called before the next_offser_store
        """
        # this should set the internal self._next_offset_store
        # to the current time.monotonic()
        await bot_state_handler.store_offset(
            bot_token=FAKE_BOT_TOKEN, offset=FAKE_OFFSET, force_store=False
        )
        assert not bot_state_handler._can_run(current=time.monotonic())

    async def test_return_when_called_at_exact_next_offset_store(
        self,
        bot_state_handler: BotStateHandler,
    ) -> None:
        """
        Test that bot_state_handler._can_run() return True
        when _can_run() was called at the the same exact time as
        the next_offset_store
        """
        current = time.monotonic()
        # patch internal time.monotonic() call
        with patch("time.monotonic", autospec=True, return_value=current):
            await bot_state_handler.store_offset(
                bot_token=FAKE_BOT_TOKEN, offset=FAKE_OFFSET, force_store=False
            )
        assert bot_state_handler._can_run(
            current=current + bot_state_handler.OFFSET_STORE_INTERVAL
        )

    async def test_return_when_called_after_next_offset_store(
        self, bot_state_handler: BotStateHandler
    ) -> None:
        """
        Test that bot_state_handler._can_run() return True
        when _can_run() was called before the next_offser_store
        """
        await bot_state_handler.store_offset(
            bot_token=FAKE_BOT_TOKEN, offset=FAKE_OFFSET, force_store=False
        )
        assert bot_state_handler._can_run(
            current=time.monotonic() + bot_state_handler.OFFSET_STORE_INTERVAL + 1
        )
