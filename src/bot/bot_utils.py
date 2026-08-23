from logging import Logger
from typing import NoReturn
from src.models.domain_model import BotUserModel
from src.exceptions import DataIntegrityError


def raise_data_integrity_error(chat_id: int, re_enter_value: str) -> NoReturn:
    """
    raise DataIntegrityError with additional information
    about what to re-input to user.
    """
    raise DataIntegrityError(
        chat_id,
        f"Error: system failure occured, please re-input your {re_enter_value} location",
    )


def get_user_data_or_raise(
    chat_id: int, user_data: BotUserModel | None, logger: Logger
) -> BotUserModel:
    if user_data is None:
        logger.error("Unexpected: missing bot_user data from the database")
        raise_data_integrity_error(chat_id, "entire")
    elif user_data.adm4_code is None:
        logger.error("Unexpected: missing adm4_code from the bot_user table")
        raise_data_integrity_error(chat_id, "entire")
    return user_data


def merge_messages(*messages: str) -> str:
    """Merge the given strings tuple into a single string."""
    return "\n\n".join(messages)
