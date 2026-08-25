import pytest
from itertools import product
from enum import Enum
from src.bot.bot_router import route_command
from src.models.enums import Commands, UserLocationState, BotAction
from src.exceptions import ActionRegistryLookupError

ALL_COMBINATIONS = product(
    [c for c in Commands], [state for state in UserLocationState], ["input_value", None]
)


class FakeEnum(Enum):
    FAKE_COMMAND = "/fake_command"


@pytest.mark.parametrize("combination", list(ALL_COMBINATIONS))
def test_route_command_all_combinations(
    combination: tuple[Commands, UserLocationState, str | None],
) -> None:
    """
    Test that route_command does not raise ActionRegistryLookupError
    when all possible combinations is passed to the function"
    """
    actions = route_command(combination[0], combination[1], combination[2])
    assert isinstance(actions, tuple)
    assert isinstance(actions[0], BotAction)


def test_route_command_with_invalid_combination() -> None:
    """
    That that route_command should raise ActionRegistryLookupError
    when an unkown combination is passed.

    In this test case, an unkown Fake Command is passed.
    """
    with pytest.raises(ActionRegistryLookupError) as exc_info:
        route_command(FakeEnum.FAKE_COMMAND, UserLocationState.NO_STATE, "fake_input")  # type: ignore[arg-type]
    assert exc_info.value.command == "FAKE_COMMAND"
    assert exc_info.value.user_state == "NO_STATE"
    assert exc_info.value.has_input_value
