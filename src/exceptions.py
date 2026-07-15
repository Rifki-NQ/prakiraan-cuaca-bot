from datetime import datetime


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

    pass


class DBNotInitializedError(QueryError):
    """Raised when the setup_db() has not called"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Error: {message}")


class EmptyCommandError(BotHandlerError):
    """Raised when user send empty text or command"""

    def __init__(self, chat_id: int) -> None:
        super().__init__(chat_id, "Error: command can't be empty")


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
