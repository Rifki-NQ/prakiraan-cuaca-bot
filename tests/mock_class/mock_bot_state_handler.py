from typing import Any
from collections.abc import Callable


class FakeBotStateHandler:
    def __init__(self) -> None:
        self.called_methods: list[Callable[..., Any]] = []
        self.called_methods_args: dict[Callable[..., Any], list[Any]] = {}

    async def get_offset(self, bot_token: str) -> int | None:
        """
        Fake implementation of get_offset for testing.

        Args:
            bot_token: 'fake_bot_token' returns a fake offset (1).
                        Any other value returns None.
        """
        self.called_methods.append(self.get_offset)
        self.called_methods_args[self.get_offset] = [bot_token]
        if bot_token == "fake_bot_token":
            return 1
        return None

    async def store_offset(self, bot_token: str, offset: int) -> None:
        self.called_methods.append(self.store_offset)
        self.called_methods_args[self.store_offset] = [bot_token, offset]

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
