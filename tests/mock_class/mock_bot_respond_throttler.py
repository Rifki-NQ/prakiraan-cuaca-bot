from typing import Any
from collections.abc import Callable


class FakeGlobalRespondThrottler:
    def __init__(self) -> None:
        self.called_methods: list[Callable[..., Any]] = []

    async def acquire(self) -> None:
        self.called_methods.append(self.acquire)

    def start_reset_timer(self) -> None:
        self.called_methods.append(self.start_reset_timer)

    def assert_called_once(
        self, method: Callable[..., Any], args: list[Any] | None = None
    ) -> None:
        assert method in self.called_methods, f"{method.__name__} has not called"


class FakeUserRespondThrottler:
    def __init__(self) -> None:
        self.called_methods: list[Callable[..., Any]] = []
        self.called_methods_args: dict[Callable[..., Any], list[Any]] = {}

    async def acquire(self, chat_id: int) -> None:
        self.called_methods.append(self.acquire)
        self.called_methods_args[self.acquire] = [chat_id]

    def start_delete_stale_data_cycle(self) -> None:
        self.called_methods.append(self.start_delete_stale_data_cycle)

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
