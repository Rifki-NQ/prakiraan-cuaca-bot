from typing import assert_never
from src.models.enums import Commands, BotAction, UserLocationState

# TODO: Add /reset location or /reset state


def route_command(
    command: Commands, user_state: UserLocationState
) -> tuple[BotAction, ...]:
    if command == Commands.START:
        match user_state:
            case UserLocationState.NO_STATE:
                return (BotAction.SHOW_INTRO, BotAction.TELLS_USER_TO_SET_LOCATION, BotAction.ASK_CITY_OR_REGENCY)
            case UserLocationState.NO_CITY_OR_REGENCY:
                return (BotAction.TELLS_USER_TO_SET_LOCATION, BotAction.ASK_CITY_OR_REGENCY,)
            case UserLocationState.NO_SUBDISTRICT:
                return (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION, BotAction.ASK_SUBDISTRICT,)
            case UserLocationState.NO_VILLAGE:
                return (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION, BotAction.ASK_VILLAGE,)
            case UserLocationState.COMPLETE:
                return (
                    BotAction.SHOW_WELCOME_BACK_INTRO,
                    BotAction.SHOW_USER_CURRENT_LOCATION,
                )
            case _:
                assert_never(user_state)
    elif command == Commands.LOCATION:
        match user_state:
            case UserLocationState.NO_STATE:
                return (BotAction.TELLS_USER_TO_SET_LOCATION, BotAction.ASK_CITY_OR_REGENCY,)
            case UserLocationState.NO_CITY_OR_REGENCY:
                return (BotAction.TELLS_USER_TO_SET_LOCATION, BotAction.ASK_CITY_OR_REGENCY,)
            case UserLocationState.NO_SUBDISTRICT:
                return (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION, BotAction.ASK_SUBDISTRICT,)
            case UserLocationState.NO_VILLAGE:
                return (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION, BotAction.ASK_VILLAGE,)
            case UserLocationState.COMPLETE:
                return (BotAction.SHOW_USER_CURRENT_LOCATION,)
            case _:
                assert_never(user_state)
    elif command == Commands.INPUT:
        match user_state:
            case UserLocationState.NO_STATE | UserLocationState.NO_CITY_OR_REGENCY:
                return (BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY,)
            case UserLocationState.NO_SUBDISTRICT:
                return (BotAction.RECEIVE_INPUT_FOR_SUBDISTRICT,)
            case UserLocationState.NO_VILLAGE:
                return (BotAction.RECEIVE_INPUT_FOR_VILLAGE,)
            case UserLocationState.COMPLETE:
                return (BotAction.TELLS_USER_NO_NEED_FOR_INPUT,)
            case _:
                assert_never(user_state)
    elif command == Commands.TODAY:
        if user_state == UserLocationState.NO_STATE:
            return (BotAction.TELLS_USER_TO_SET_LOCATION,)
        elif user_state != UserLocationState.COMPLETE:
            return (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,)
        else:
            return (BotAction.SHOW_TODAY_FORECASTS,)
    elif command == Commands.TOMORROW:
        if user_state == UserLocationState.NO_STATE:
            return (BotAction.TELLS_USER_TO_SET_LOCATION,)
        elif user_state != UserLocationState.COMPLETE:
            return (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,)
        else:
            return (BotAction.SHOW_TOMORROW_FORECASTS,)
    else:
        assert_never(command)
