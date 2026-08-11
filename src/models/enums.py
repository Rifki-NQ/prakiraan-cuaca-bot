from enum import Enum, auto


class Commands(Enum):
    START = "/start"
    LOCATION = "/location"
    INPUT = "/input"
    TODAY = "/today"
    TOMORROW = "/tomorrow"


class BotAction(Enum):
    SHOW_INTRO = auto()
    ASK_CITY_OR_REGENCY = auto()
    ASK_SUBDISTRICT = auto()
    ASK_VILLAGE = auto()
    SHOW_USER_CURRENT_LOCATION = auto()
    SHOW_WELCOME_BACK_INTRO = auto()
    SHOW_TODAY_FORECASTS = auto()
    SHOW_TOMORROW_FORECASTS = auto()
    TELLS_USER_TO_SET_LOCATION = auto()
    TELLS_USER_NO_NEED_FOR_INPUT = auto()
    TELLS_USER_TO_FINISH_SET_LOCATION = auto()
    RECEIVE_INPUT_FOR_CITY_OR_REGENCY = auto()
    RECEIVE_INPUT_FOR_SUBDISTRICT = auto()
    RECEIVE_INPUT_FOR_VILLAGE = auto()


class UserLocationState(Enum):
    NO_STATE = auto()
    NO_CITY_OR_REGENCY = auto()
    NO_SUBDISTRICT = auto()
    NO_VILLAGE = auto()
    COMPLETE = auto()
