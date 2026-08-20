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
            BotAction.TELLS_USER_TO_SET_LOCATION,
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
]


# TODO: move empty /input value detection from bot_respond_handler
#       to bot_router
INPUT_COMMAND_REGISTRY: list[ActionEntry] = [
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_STATE,
        need_input_value=False,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_CITY_OR_REGENCY,
        need_input_value=False,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_SUBDISTRICT,
        need_input_value=False,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_SUBDISTRICT,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.NO_VILLAGE,
        need_input_value=False,
        bot_action=(BotAction.RECEIVE_INPUT_FOR_VILLAGE,),
    ),
    ActionEntry(
        command=Commands.INPUT,
        user_state=UserLocationState.COMPLETE,
        need_input_value=False,
        bot_action=(BotAction.TELLS_USER_NO_NEED_FOR_INPUT,),
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
]


COMMANDS_REGISTRY: list[ActionEntry] = [
    *START_COMMAND_REGISTRY,
    *HELP_COMMAND_REGISTRY,
    *LOCATION_COMMAND_REGISTRY,
    *INPUT_COMMAND_REGISTRY,
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
