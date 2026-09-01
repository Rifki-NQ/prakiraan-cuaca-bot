import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from src.bot.bot_state_handler import BotStateHandler


@pytest.fixture
def bot_state_handler() -> BotStateHandler:
    fake_offset = Mock(offset=123)
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


async def test_get_bot_offset_return_expected(
    bot_state_handler: BotStateHandler,
) -> None:
    result = await bot_state_handler.get_offset("fake_token")
    assert result is not None
    assert result == 123


async def test_get_bot_offset_when_offset_is_none(
    bot_state_handler_none_offset: BotStateHandler,
) -> None:
    """
    Test if get_offset() return None when the query layer return
    Row object without the offset data.
    """
    result = await bot_state_handler_none_offset.get_offset("fake_token")
    assert result is None


async def test_get_bot_offset_when_row_is_none(
    bot_state_handler_none_row: BotStateHandler,
) -> None:
    """
    Test if get_offset() return None when the query layer return None
    instead of a Row object.
    """
    result = await bot_state_handler_none_row.get_offset("fake_token")
    assert result is None


async def test_store_offset_can_run_is_true(
    bot_state_handler: BotStateHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    # patch bot_state_handler._can_run() return True
    with patch.object(bot_state_handler, "_can_run", return_value=True):
        await bot_state_handler.store_offset("fake_token", 123)
    bot_state_handler.query.insert_or_update_bot_offset.assert_called_once()  # type: ignore[attr-defined]
    assert "offset store" in caplog.messages[0]
    assert "skip offset store" not in caplog.messages[0]


async def test_store_offset_can_run_is_false(
    bot_state_handler: BotStateHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    # patch bot_state_handler._can_run() return False
    with patch.object(bot_state_handler, "_can_run", return_value=False):
        await bot_state_handler.store_offset("fake_token", 123)
    bot_state_handler.query.insert_or_update_bot_offset.assert_not_called()  # type: ignore[attr-defined]
    assert "skip offset store" in caplog.messages[0]


def test_can_run_call_last_offset_store_is_none(
    bot_state_handler: BotStateHandler,
) -> None:
    """
    Test if bot_state_handler._can_run() return False,
    when self._last_offset_store is None.
    """
    # explicitly making the attr to None
    bot_state_handler._last_offset_store = None  # pyright: ignore[reportPrivateUsage]
    result = bot_state_handler._can_run(Mock())  # pyright: ignore[reportPrivateUsage]
    assert result


def test_can_run_call_under_time_interval(bot_state_handler: BotStateHandler) -> None:
    """
    Test if bot_state_handler._can_run() return False,
    when current_datetime minus self._last_offset_interval is under
    the OFFSET_STORE_INTERVAL.
    """
    last_offset_store_dt = datetime(2020, 1, 1, 1, 1, 1)
    current_dt = datetime(2020, 1, 1, 1, 1, 11)
    # making sure the mocked datetime interval is
    # less or equal to current OFFSET_STORE_INTERVAL
    interval = current_dt - last_offset_store_dt
    assert interval.total_seconds() < BotStateHandler.OFFSET_STORE_INTERVAL
    bot_state_handler._last_offset_store = last_offset_store_dt  # pyright: ignore[reportPrivateUsage]
    result = bot_state_handler._can_run(current_datetime=current_dt)  # pyright: ignore[reportPrivateUsage]
    assert not result


def test_can_run_call_over_time_interval(bot_state_handler: BotStateHandler) -> None:
    """
    Test if bot_state_handler._can_run() return True,
    when current_datetime minus self._last_offset_interval is over
    the OFFSET_STORE_INTERVAL.
    """
    last_offset_store_dt = datetime(2020, 1, 1, 1, 1, 1)
    current_dt = datetime(2020, 1, 1, 1, 1, 40)
    # making sure the mocked datetime interval is
    # over the current OFFSET_STORE_INTERVAL
    interval = current_dt - last_offset_store_dt
    assert interval.total_seconds() > BotStateHandler.OFFSET_STORE_INTERVAL
    bot_state_handler._last_offset_store = last_offset_store_dt  # pyright: ignore[reportPrivateUsage]
    result = bot_state_handler._can_run(current_datetime=current_dt)  # pyright: ignore[reportPrivateUsage]
    assert result
    
    
def test_can_run_call_exact_time_interval(
    bot_state_handler: BotStateHandler
) -> None:
    """
    Test if bot_state_handler._can_run() return True,
    when current_datetime minus self._last_offset_interval 
    is the same with OFFSET_STORE_INTERVAL.
    """
    last_offset_store_dt = datetime(2020, 1, 1, 1, 1, 1)
    current_dt = datetime(2020, 1, 1, 1, 1, 31)
    # making sure the mocked datetime interval is
    # the same as the current OFFSET_STORE_INTERVAL
    interval = current_dt - last_offset_store_dt
    assert interval.total_seconds() == BotStateHandler.OFFSET_STORE_INTERVAL
    bot_state_handler._last_offset_store = last_offset_store_dt  # pyright: ignore[reportPrivateUsage]
    result = bot_state_handler._can_run(current_datetime=current_dt)  # pyright: ignore[reportPrivateUsage]
    assert result