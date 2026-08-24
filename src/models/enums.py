from enum import Enum, IntEnum, auto


class Commands(Enum):
    START = "/start"
    HELP = "/help"
    LOCATION = "/location"
    INPUT = "/input"
    RESET = "/reset"
    REVERT = "/revert"
    TODAY = "/today"
    TOMORROW = "/tomorrow"


class BotAction(Enum):
    SHOW_INTRO = auto()
    SHOW_HELP = auto()
    SHOW_EXTRA_HELP = auto()
    ASK_CITY_OR_REGENCY = auto()
    ASK_SUBDISTRICT = auto()
    ASK_VILLAGE = auto()
    SHOW_USER_CURRENT_LOCATION = auto()
    SHOW_WELCOME_BACK_INTRO = auto()
    SHOW_TODAY_FORECASTS = auto()
    SHOW_TOMORROW_FORECASTS = auto()
    TELLS_USER_TO_SET_LOCATION = auto()
    TELLS_USER_LOCATION_SETUP_FINISHED = auto()
    TELLS_USER_TO_FINISH_SET_LOCATION = auto()
    TELLS_USER_TO_ADD_INPUT_VALUE = auto()
    RECEIVE_INPUT_FOR_CITY_OR_REGENCY = auto()
    RECEIVE_INPUT_FOR_SUBDISTRICT = auto()
    RECEIVE_INPUT_FOR_VILLAGE = auto()
    RESET_USER_LOCATION = auto()
    TELLS_USER_NO_NEED_FOR_RESET = auto()
    REVERT_USER_LOCATION_STATE = auto()
    TELLS_USER_NO_NEED_FOR_REVERT = auto()
    TELLS_USER_NO_NEED_FOR_INPUT_VALUE = auto()


class UserLocationState(Enum):
    NO_STATE = auto()
    NO_CITY_OR_REGENCY = auto()
    NO_SUBDISTRICT = auto()
    NO_VILLAGE = auto()
    COMPLETE = auto()


class UserStateCheckLevel(IntEnum):
    """Used in src/bot/location_flow_handler.py"""

    CITY_OR_REGENCY = auto()
    SUBDISTRICT = auto()
    VILLAGE = auto()


class UserDataRestorationResult(Enum):
    """Used in src/bot/bot_respond_handler.py"""

    SUCCESS = auto()
    FAILED = auto()
