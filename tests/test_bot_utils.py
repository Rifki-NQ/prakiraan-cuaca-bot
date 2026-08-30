import pytest
from src.main import logger  # borrow a logger from src.main
from src.bot.bot_utils import (
    raise_data_integrity_error,
    get_user_data_or_raise,
    merge_messages,
)
from src.models.domain_model import BotUserModel
from src.exceptions import DataIntegrityError


def test_raise_data_integrity_error() -> None:
    with pytest.raises(DataIntegrityError) as exc_info:
        raise_data_integrity_error(123, "entire")
    assert exc_info.value.chat_id == 123
    assert "re-input your entire" in exc_info.value.message


def test_get_user_data_or_raise_with_none_user_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(10)
    user_data = None
    with pytest.raises(DataIntegrityError) as exc_info:
        get_user_data_or_raise(123, user_data, logger)
    assert exc_info.value.chat_id == 123
    assert "re-input your entire" in exc_info.value.message
    assert "missing bot_user data" in caplog.messages[0]


def test_get_user_data_or_raise_with_none_adm4_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when the user_data exist but has no adm4_code"""
    user_data = BotUserModel(chat_id=123, username=None, adm4_code=None)
    with pytest.raises(DataIntegrityError) as exc_info:
        get_user_data_or_raise(123, user_data, logger)
    assert exc_info.value.chat_id == user_data.chat_id
    assert "re-input your entire" in exc_info.value.message
    assert "missing adm4_code" in caplog.messages[0]


def test_merge_messages_return_expected() -> None:
    messages = ["message a", "message b"]
    output = merge_messages(*messages)
    assert (
        output
        == """message a

message b"""
    )
