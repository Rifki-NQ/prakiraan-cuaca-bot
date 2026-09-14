from typing import Any
from collections.abc import Callable
from src.models.enums import Commands


class FakeBotRespondHandler:
    def __init__(self) -> None:
        self.called_methods: list[Callable[..., Any]] = []
        self.called_methods_args: dict[Callable[..., Any], list[Any]] = {}

    async def parse_command(
        self, chat_id: int, command: Commands, input_value: str | None = None
    ) -> str:
        self.called_methods.append(self.parse_command)
        self.called_methods_args[self.parse_command] = [chat_id, command, input_value]
        return "fake respond message"

    def assert_called_once_with(
        self, method: Callable[..., Any], args: list[Any] | None = None
    ) -> None:
        assert method in self.called_methods, f"{method.__name__} has not called"
        if args is not None:
            method_args = self.called_methods_args.get(method, None)
            if method_args is None:
                assert False, f"{method.__name__} takes no arguments"
            assert args == method_args, (
                f"{method.__name__} args assertion failed, "
                f"expected: {method_args}, "
                f"got: {args}"
            )
