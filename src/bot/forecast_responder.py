import logging
from collections.abc import Callable, AsyncIterable
from src.models.domain_model import ForecastModel, BotUserModel
from src.bot import message_container
from src.bot.bot_utils import get_user_data_or_raise, merge_messages
from src.exceptions import EmptyQueryResultError, NoForecastResultError

logger = logging.getLogger(__name__)


async def get_merged_forecasts(
    chat_id: int,
    user_data: BotUserModel | None,
    get_forecast_service: Callable[[str], AsyncIterable[ForecastModel]],
) -> str:
    user_data = get_user_data_or_raise(chat_id, user_data, logger)
    assert user_data.adm4_code is not None, (
        "get_user_data_or_raise() guarantee this attribute is not None"
    )
    merged_forecasts: list[str] = []
    try:
        add_header = True
        async for forecast in get_forecast_service(user_data.adm4_code):
            if add_header:
                # add forecast header as the first merged_forecasts value
                merged_forecasts.append(
                    message_container.forecasts_message_header(
                        user_data.adm4_code,
                        forecast.forecast_datetime.strftime("%d %B %Y"),
                    )
                )
            add_header = False
            merged_forecasts.append(
                message_container.format_one_forecast(
                    forecast_time=forecast.forecast_datetime.strftime("%H:%M"),
                    temp=forecast.temperature,
                    ttc=forecast.total_cloud_coverage,
                    tp=forecast.total_precipitation,
                    weat_desc=forecast.weather_description_eng,
                    humidity=forecast.humidity,
                    ws=forecast.wind_speed,
                    visibility=forecast.visibility,
                )
            )
        return merge_messages(*merged_forecasts)
    except EmptyQueryResultError as e:
        raise NoForecastResultError(
            chat_id,
            message_container.no_forecast_result_error_message(
                user_data.adm4_code, e.query.get("start_dt"), e.query.get("end_dt")
            ),
        )
