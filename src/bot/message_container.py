from src.models.domain_model import BotUserStateModel

SHOW_INTRO = """Welcome to prakiraan-cuaca-bot!

This is an experimental project by https://github.com/Rifki-NQ, built for learning purposes.
It delivers weather forecasts collected by https://github.com/Rifki-NQ/indo-weather-etl

Type /help to see the available commands."""


SHOW_HELP = """<b>Available commands</b>
/start - Start the bot
/help - Show this help message
/location - Continue your location setup, or show your current location
/input - Send a value to the bot
/today - Show today's weather forecast
/tomorrow - Show tomorrow's weather forecast
/reset - Clear your location setup and start over
/revert - Go back one step in your location setup

<b>Detailed help</b>
/help location - More about /location
/help input - More about /input
/help today - More about /today
/help tomorrow - More about /tomorrow
/help reset - More about /reset
/help revert - More about /revert
"""


SHOW_WELCOME_BACK_INTRO = "Welcome back to prakiraan-cuaca-bot!"


ASK_CITY_OR_REGENCY = """Let's set up your location.
Send your <b>city or regency</b> with /input <b>your city or regency</b>

<i>Example: /input kabupaten bekasi</i>"""


TELLS_USER_LOCATION_SETUP_FINISHED = (
    "Your location is already set up, so there's no need to use /input."
)

TELLS_USER_TO_SET_LOCATION = (
    "Please set your location first. Use /location to get started."
)

TELLS_USER_TO_FINISH_SET_LOCATION = (
    "Please finish your location setup first. Use /location to continue."
)

TELLS_USER_NO_NEED_FOR_RESET = "There's no location setup to reset."

TELLS_USER_RESET_SUCCESS = (
    "Your location has been reset. Use /location to set it up again."
)

TELLS_USER_NO_NEED_FOR_REVERT = "There's nothing to revert yet."


def notify_to_add_input_value(command: str) -> str:
    return f"The {command} command needs a value. Please add it after the command."


def notify_to_not_add_input_value(command: str) -> str:
    return f"The {command} command doesn't take a value. Please send it on its own."


def show_revert_message(reverted_state: str) -> str:
    return f"<b>{reverted_state}</b> has been removed from your location setup."


def notify_city_or_regency_not_found(city_or_regency: str | None) -> str:
    return f"Sorry, <b>{city_or_regency}</b> wasn't found. Please check the spelling and try again."


def notify_to_choose_city_or_regency(city_or_regency_list: str) -> str:
    return f"""Choose your <b>city or regency</b> from the list below
using /input <b>your city or regency</b>
{city_or_regency_list}

<i>Example: /input kabupaten bekasi</i>"""


def notify_city_or_regency_updated(city_or_regency: str) -> str:
    return f"Your <b>city or regency</b> has been set to <b>{city_or_regency}</b>."


def notify_subdistrict_not_found(subdistrict: str | None, subdistrict_list: str) -> str:
    return f"""Sorry, <b>{subdistrict}</b> wasn't found. Please choose from the list below
using /input <b>your subdistrict</b>
{subdistrict_list}

<i>Example: /input cikarang selatan</i>"""


def notify_subdistrict_updated(subdistrict: str) -> str:
    return f"Your <b>subdistrict</b> has been set to <b>{subdistrict}</b>."


def notify_to_choose_subdistrict(subdistrict_list: str) -> str:
    return f"""Choose your <b>subdistrict</b> from the list below
using /input <b>your subdistrict</b>
{subdistrict_list}

<i>Example: /input cikarang selatan</i>"""


def notify_village_not_found(village: str | None, village_list: str) -> str:
    return f"""Sorry, <b>{village}</b> wasn't found. Please choose from the list below
using /input <b>your village</b>
{village_list}

<i>Example: /input sukamahi</i>"""


def notify_village_updated(village: str) -> str:
    return f"Your <b>village</b> has been set to <b>{village}</b>."


def notify_to_choose_village(village_list: str) -> str:
    return f"""Choose your <b>village</b> from the list below
using /input <b>your village</b>
{village_list}

<i>Example: /input sukamahi</i>"""


def notify_location_updated(user_state: BotUserStateModel, adm4_code: str) -> str:
    return f"""Your location has been saved!

City or regency: <b>{user_state.kabupaten_atau_kota}</b>
Subdistrict: <b>{user_state.kecamatan}</b>
Village: <b>{user_state.desa_atau_kelurahan}</b>
Area code (ADM4): <b>{adm4_code}</b>"""


def show_user_full_address(
    city_or_regency: str, subdistrict: str, village: str, adm4_code: str
) -> str:
    return f"""📍 <b>Your location</b>

City or regency: <b>{city_or_regency}</b>
Subdistrict: <b>{subdistrict}</b>
Village: <b>{village}</b>
Area code (ADM4): <b>{adm4_code}</b>"""


def forecasts_message_header(adm4_code: str, date: str) -> str:
    return f"📍 <b>Forecast for area {adm4_code}</b>\n🗓 As of {date}\n"


def format_one_forecast(
    forecast_time: str,
    temp: int,
    ttc: int | None,
    tp: float | None,
    weat_desc: str | None,
    ws: float | None,
    humidity: int | None,
    visibility: int | None,
) -> str:
    return (
        f"⏰ <b>{forecast_time}</b>\n"
        f"   {weat_desc if weat_desc is not None else 'No description'}\n"
        f"🌡 Temperature: {temp}°C\n"
        f"💧 Humidity: {add_unit(humidity, '%')}\n"
        f"☁️ Cloud cover: {add_unit(ttc, '%')}\n"
        f"🌧 Precipitation: {add_unit(tp, ' mm')}\n"
        f"💨 Wind: {add_unit(ws, ' km/h')}\n"
        f"👁 Visibility: {add_unit(visibility, ' m')}\n"
    )


def add_unit(value: float | None, unit: str) -> str:
    if value is not None:
        return f"{value}{unit}"
    return "No data"


def no_forecast_result_error_message(
    adm4_code: str, start_dt: str | None, end_dt: str | None
) -> str:
    return f"""Sorry, no forecast is available for area <b>{adm4_code}</b>
between {start_dt} and {end_dt}. Please try again later."""


def show_invalid_extra_help_value_message(help_value: str) -> str:
    return f"Sorry, there's no detailed help for <b>{help_value}</b>. Type /help to see the available topics."


SHOW_LOCATION_COMMAND_HELP = """<b>/location</b>
Continues your location setup.
If your setup is already finished, it shows your current location instead."""


SHOW_INPUT_COMMAND_HELP = """<b>/input value</b>
Sends a value to the bot.
Right now it's only used during location setup, to enter your city or regency, subdistrict, and village."""


SHOW_TODAY_COMMAND_HELP = """<b>/today</b>
Shows today's weather forecast.
Available once your location setup is finished."""


SHOW_TOMORROW_COMMAND_HELP = """<b>/tomorrow</b>
Shows tomorrow's weather forecast.
Available once your location setup is finished."""


SHOW_RESET_COMMAND_HELP = """<b>/reset</b>
Clears your whole location setup so you can start over.
Only available while your setup is in progress.
To go back just one step instead, use /revert."""


SHOW_REVERT_COMMAND_HELP = """<b>/revert</b>
Goes back one step in your location setup (for example, from village back to subdistrict).
Only available while your setup is in progress.
To start over completely, use /reset."""
