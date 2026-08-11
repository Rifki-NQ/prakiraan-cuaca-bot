from typing import NoReturn
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
