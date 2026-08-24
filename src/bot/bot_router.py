from src.models.domain_model import ActionEntry
from src.models.enums import Commands, BotAction, UserLocationState
from src.exceptions import ActionRegistryLookupError


# TODO: add /reset command

START_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.START,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(
            BotAction.SHOW_INTRO,
            BotAction.ASK_CITY_OR_REGENCY,
        ),
    ),
    ActionEntry(
        command=Commands.START,
        user_state=UserLocationState.NO_CITY_OR_REGENCY,
        need_input_value=False,
        bot_action=(
            BotAction.TELLS_USER_TO_SET_LOCATION,
            BotAction.ASK_CITY_OR_REGENCY,
        ),
    ),
    ActionEntry(
        command=Commands.START,
        user_state=UserLocationState.NO_SUBDISTRICT,
        need_input_value=False,
        bot_action=(
            BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,
            BotAction.ASK_SUBDISTRICT,
        ),
    ),
    ActionEntry(
        command=Commands.START,
        user_state=UserLocationState.NO_VILLAGE,
        need_input_value=False,
        bot_action=(
            BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,
            BotAction.ASK_VILLAGE,
        ),
    ),
    ActionEntry(
        command=Commands.START,
        user_state=UserLocationState.COMPLETE,
        need_input_value=False,
        bot_action=(
            BotAction.SHOW_WELCOME_BACK_INTRO,
            BotAction.SHOW_USER_CURRENT_LOCATION,
        ),
    ),
    # in case user send /start with value
    ActionEntry(
        command=Commands.START,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
    ),
]


HELP_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.HELP,
        user_state=None,
        need_input_value=False,
        bot_action=(BotAction.SHOW_HELP,),
    ),
    ActionEntry(
        command=Commands.HELP,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.SHOW_EXTRA_HELP,),
    ),
]

LOCATION_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.LOCATION,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(
            BotAction.TELLS_USER_TO_SET_LOCATION,
            BotAction.ASK_CITY_OR_REGENCY,
        ),
    ),
    ActionEntry(
        command=Commands.LOCATION,
        user_state=UserLocationState.NO_CITY_OR_REGENCY,
        need_input_value=False,
        bot_action=(
            BotAction.TELLS_USER_TO_SET_LOCATION,
            BotAction.ASK_CITY_OR_REGENCY,
        ),
    ),
    ActionEntry(
        command=Commands.LOCATION,
        user_state=UserLocationState.NO_SUBDISTRICT,
        need_input_value=False,
        bot_action=(
            BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,
            BotAction.ASK_SUBDISTRICT,
        ),
    ),
    ActionEntry(
        command=Commands.LOCATION,
        user_state=UserLocationState.NO_VILLAGE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION, BotAction.ASK_VILLAGE),
    ),
    ActionEntry(
        command=Commands.LOCATION,
        user_state=UserLocationState.COMPLETE,
        need_input_value=False,
        bot_action=(BotAction.SHOW_USER_CURRENT_LOCATION,),
    ),
    # in case user send /location with value
    ActionEntry(
        command=Commands.LOCATION,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
    ),
]


INPUT_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_STATE,
        need_input_value=True,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_CITY_OR_REGENCY,
        need_input_value=True,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_SUBDISTRICT,
        need_input_value=True,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_SUBDISTRICT,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_VILLAGE,
        need_input_value=True,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_VILLAGE,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.COMPLETE,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_LOCATION_SETUP_FINISHED,),
    ),
    # in case user send /input without any value
    ActionEntry(
        command=Commands.INPUT,
        user_state=None,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_ADD_INPUT_VALUE,),
    ),
]


RESET_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.RESET,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_RESET,),
    ),
    ActionEntry(
        command=Commands.RESET,
        user_state=None,
        need_input_value=False,
        bot_action=(BotAction.RESET_USER_LOCATION,),
    ),
    # in case user send /reset with value
    ActionEntry(
        command=Commands.RESET,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
    ),
]


REVERT_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.REVERT,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_REVERT,),
    ),
    ActionEntry(
        command=Commands.REVERT,
        user_state=None,
        need_input_value=False,
        bot_action=(BotAction.REVERT_USER_LOCATION_STATE,),
    ),
    # in case user send /revert with value
    ActionEntry(
        command=Commands.REVERT,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
    ),
]


TODAY_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.TODAY,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TODAY,
        user_state=UserLocationState.NO_CITY_OR_REGENCY,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TODAY,
        user_state=UserLocationState.NO_SUBDISTRICT,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TODAY,
        user_state=UserLocationState.NO_VILLAGE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TODAY,
        user_state=UserLocationState.COMPLETE,
        need_input_value=False,
        bot_action=(BotAction.SHOW_TODAY_FORECASTS,),
    ),
    # in case user send /today with value
    ActionEntry(
        command=Commands.TODAY,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
    ),
]


TOMORROW_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.TOMORROW,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TOMORROW,
        user_state=UserLocationState.NO_CITY_OR_REGENCY,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TOMORROW,
        user_state=UserLocationState.NO_SUBDISTRICT,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TOMORROW,
        user_state=UserLocationState.NO_VILLAGE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
    ),
    ActionEntry(
        command=Commands.TOMORROW,
        user_state=UserLocationState.COMPLETE,
        need_input_value=False,
        bot_action=(BotAction.SHOW_TOMORROW_FORECASTS,),
    ),
    # in case user send /tomorrow with value
    ActionEntry(
        command=Commands.TOMORROW,
        user_state=None,
        need_input_value=True,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
    ),
]


COMMANDS_REGISTRY: list[ActionEntry] = [
    *START_COMMAND_REGISTRY,
    *HELP_COMMAND_REGISTRY,
    *LOCATION_COMMAND_REGISTRY,
    *INPUT_COMMAND_REGISTRY,
    *RESET_COMMAND_REGISTRY,
    *REVERT_COMMAND_REGISTRY,
    *TODAY_COMMAND_REGISTRY,
    *TOMORROW_COMMAND_REGISTRY,
]


# turn the registered command, user_state and need_input_value bool
# into a composite key to achieve O(1) time complexity
REGISTERED_ACTIONS = {
    (e.command, e.user_state, e.need_input_value): e.bot_action
    for e in COMMANDS_REGISTRY
}


def route_command(
    command: Commands, user_state: UserLocationState, input_value: str | None
) -> tuple[BotAction, ...]:
    has_input_value = input_value is not None
    actions = REGISTERED_ACTIONS.get((command, user_state, has_input_value), None)
    if actions is not None:
        return actions
    # try get the actions where user_state replaced with None
    # the None replacement in user_state means the command
    # does not care about the user_state at all
    actions = REGISTERED_ACTIONS.get((command, None, has_input_value), None)
    if actions is not None:
        return actions
    raise ActionRegistryLookupError(
        command.name.upper(), user_state.name.upper(), has_input_value
    )
