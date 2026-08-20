from datetime import datetime
from src.models.enums import UserLocationState


class DomainError(Exception):
    """Base class for all domain/business error"""

    pass


class QueryError(DomainError):
    """Base class for all query related error"""

    pass


class BotHandlerError(DomainError):
    """Base class for all bot handler error"""

    def __init__(self, chat_id: int, message: str) -> None:
        self.chat_id = chat_id
        self.message = message
        super().__init__(message)


class ActionRegistryLookupError(DomainError):
    """
    Raised by src/bot_router.route_command() when no BotAction is
    registered for the incoming (command, user_state, need_input_value)
    combination.
    """

    def __init__(self, command: str, user_state: str, has_input_value: bool) -> None:
        self.command = command
        self.user_state = user_state
        self.has_input_value = has_input_value
        super().__init__(
            "Error: no BotAction registered for this combination"
            f" (command: {command}, user_state: {user_state}, has_input_value: {str(has_input_value)})"
        )


class InvalidDatetimeRangeError(QueryError):
    """Raised when the start datetime is greater than the end datetime"""

    def __init__(self, start_dt: datetime, end_dt: datetime) -> None:
        self.start_dt = start_dt
        self.end_dt = end_dt
        super().__init__(
            f"Error: start_dt ({start_dt}) cannot be greater than end_dt ({end_dt})"
        )


class EmptyQueryResultError(QueryError):
    """Raised when the query return zero result"""

    def __init__(self, query: dict[str, str]) -> None:
        self.query = query
        super().__init__(
            f"Error: no result from query; {', '.join(f'{k}={v}' for k, v in query.items())}"
        )


class DBNotInitializedError(QueryError):
    """Raised when the setup_db() has not called"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Error: {message}")


class EmptyCommandError(BotHandlerError):
    """Raised when user send empty text or command"""

    def __init__(self, chat_id: int) -> None:
        super().__init__(chat_id, "Error: command can't be empty")


class NoForecastResultError(BotHandlerError):
    """
    Raised when the weather forecast is not found
    for this specific adm4_code and datetime_range
    """

    def __init__(self, chat_id: int, message: str) -> None:
        super().__init__(chat_id, message)


class InvalidCommandError(BotHandlerError):
    """Raised when user send invalid command"""

    def __init__(self, chat_id: int, command: str) -> None:
        self.command = command
        super().__init__(chat_id, f"Error: {command} is not a recognized command")


class NotCommandTypeError(BotHandlerError):
    """Raised when user send non command text"""

    def __init__(self, chat_id: int, text: str) -> None:
        self.text = text
        super().__init__(chat_id, f"Error: {text} is not a command")


class InvalidUserStateError(BotHandlerError):
    """Raised when user current state is invalid"""

    def __init__(
        self, chat_id: int, message: str, current_user_state: UserLocationState
    ) -> None:
        self.current_user_state = current_user_state
        super().__init__(chat_id, message)


class EmptyInputValueError(BotHandlerError):
    """
    Raised when user type /input command without giving any value after that

    valid example: /input value_a

    invalid example: /input
    """

    pass


class DataIntegrityError(BotHandlerError):
    """Raised when the data from the database does not exist or valid,
    when it's expected to exist or valid"""

    def __init__(self, chat_id: int, message: str) -> None:
        super().__init__(chat_id, message)


class SendMessageRetryExhaustedError(BotHandlerError):
    """Raised when the retry attempt has reached for Bot.send_message()"""

    def __init__(self, chat_id: int, retry_attempt: int, dropped_message: str) -> None:
        self.chat_id = chat_id
        self.retry_attempt = retry_attempt
        self.dropped_message = dropped_message
        super().__init__(
            chat_id,
            f"send_message retry attempt reached: {retry_attempt}, "
            f"chat_id: {chat_id}, "
            f"dropped_message: {dropped_message}",
        )
