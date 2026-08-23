"""This module contains all user facing messages"""

SHOW_INTRO = """Welcome to prakiraan-cuaca-bot project.
this is an experimental project made by https://github.com/Rifki-NQ.
specifically created for learning purpose,
as the consumer layer of
https://github.com/Rifki-NQ/indo-weather-etl"""


SHOW_HELP = """Available Commands:
/start
    <b>start the bot</b>
/help
    <b>show this help message</b>
/location
    <b>show your current location</b>
/input
    <b>send value to the bot</b>
/today
    <b>show today weather forecast</b>
/tomorrow
    <b>show tomorrow weather forecast</b>

Extra help commands:
/help location
    <b>Show extra help for /location command</b>
/help input
    <b>Show extra help for /input command</b>
/help today
    <b>Show extra help for /today command</b>
/help tomorrow
    <b>Show extra help for /tomorrow command</b>"""


SHOW_WELCOME_BACK_INTRO = """Welcome back to prakiraan-cuaca-bot project"""


ASK_CITY_OR_REGENCY = """Enter your <b>city or regency</b> location
with /input <b>your city or regency</b>.

<i>example: /input kabupaten bekasi</i>"""


TELLS_USER_NO_NEED_FOR_INPUT = "Location setup finished, no need for /input"

TELLS_USER_TO_ADD_INPUT_VALUE = "Input value is required after /input command"

TELLS_USER_TO_SET_LOCATION = "Set your location first to get started"

TELLS_USER_TO_FINISH_SET_LOCATION = "Finish your location setup to get started"


def notify_city_or_regency_not_found(city_or_regency: str | None) -> str:
    return f"<b>{city_or_regency}</b> not found, please retry"


def notify_to_choose_city_or_regency(city_or_regency_list: str) -> str:
    return f"""Select your <b>city or regency</b> from the list below
with /input <b>your city or regency</b>
{city_or_regency_list}

<i>example: /input kabupaten bekasi</i>"""


def notify_city_or_regency_updated(city_or_regency: str) -> str:
    return f"Your <b>city or regency</b> location updated to <b>{city_or_regency}</b>."


def notify_subdistrict_not_found(subdistrict: str | None, subdistrict_list: str) -> str:
    return f"""<b>{subdistrict}</b> not found, select from the list below
with /input <b>your city or subdistrict</b>
{subdistrict_list}

<i>example: /input cikarang selatan</i>"""


def notify_subdistrict_updated(subdistrict: str) -> str:
    return f"Your <b>subdistrict</b> location updated to <b>{subdistrict}</b>."


def notify_to_choose_subdistrict(subdistrict_list: str) -> str:
    return f"""Select your <b>subdistrict</b> from the list below
with /input <b>your subdistrict</b>
{subdistrict_list}

<i>example: /input cikarang selatan</i>"""


def notify_village_not_found(village: str | None, village_list: str) -> str:
    return f"""<b>{village}</b> not found, select from the list below
with /input <b>your village</b>
{village_list}

<i>example: /input sukamahi</i>
"""


def notify_village_updated(village: str) -> str:
    return f"Your <b>village</b> location updated to <b>{village}</b>."


def notify_to_choose_village(village_list: str) -> str:
    return f"""Select your <b>village</b> from the list below
with /input <b>your village</b>
{village_list}

<i>example: /input sukamahi</i>
"""


def notify_location_updated(
    city_or_regency: str, subdistrict: str, village: str, adm4_code: str
) -> str:
    return f"""
Your location address updated!
city or regency: <b>{city_or_regency}</b>
subdistrict: <b>{subdistrict}</b>
village: <b>{village}</b>
adm4_code of the address: <b>{adm4_code}</b>
"""


def show_user_full_address(
    city_or_regency: str, subdistrict: str, village: str, adm4_code: str
) -> str:
    return f"""
-- Your location address --
city or regency: <b>{city_or_regency}</b>
subdistrict: <b>{subdistrict}</b>
village: <b>{village}</b>
adm4_code of the address: <b>{adm4_code}</b>
"""


def forecasts_message_header(adm4_code: str, date: str) -> str:
    return f"📍 <b>Forecast for {adm4_code}</b>\n🗓 As of {date}\n"


# see the params name detail in src/models/domain_model.ForecastModel
def format_one_forecast(
    forecast_time: str,
    temp: int,
    ttc: int,
    tp: float,
    weat_desc: str,
    ws: float,
    humidity: int,
    visibility: int,
) -> str:
    return (
        f"⏰ <b>{forecast_time}</b>\n"
        f"   {weat_desc}\n"
        f"🌡 Temp: {temp}°C\n"
        f"💧 Humidity: {humidity}%\n"
        f"☁️ Cloud Cover: {ttc}%\n"
        f"🌧 Precipitation: {tp} mm\n"
        f"💨 Wind: {ws} km/h\n"
        f"👁 Visibility: {visibility} km\n"
    )


def no_forecast_result_error_message(
    adm4_code: str, start_dt: str | None, end_dt: str | None
) -> str:
    return f"""Error: weather forecast not found for <b>{adm4_code}</b>
datetime range: {start_dt} to {end_dt}"""


def show_invalid_extra_help_value_message(
    help_value: str
) -> str:
    return f"<b>/help {help_value}</b> is not a known extra help"

SHOW_LOCATION_COMMAND_HELP = """<b>/location</b>
Continue location setup,
if they have finished the setup,
this command will show
their current location instead"""


SHOW_INPUT_COMMAND_HELP = """<b>/input value</b>
Send an input to the bot,
as of now, this is only used in location setup
to send the location name to the bot"""
    

SHOW_TODAY_COMMAND_HELP = """<b>/today</b>
Get today weather forecast,
user can only use this if they have finished
the location setup"""
    
    
SHOW_TOMORROW_COMMAND_HELP = """<b>/tomorrow</b>
Get tomorrow weather forecast,
user can only use this if they have finished
the location setup"""