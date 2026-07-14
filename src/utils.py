from collections.abc import AsyncIterable
from src.models.domain_model import ForecastModel


def convert_forecast(forecast_data: ForecastModel) -> str:
    """Convert single ForecastModel into str."""
    return f"""forecast_datetime: {forecast_data.forecast_datetime}
adm4_code: {forecast_data.adm4_code}
temperature: {forecast_data.temperature}
humidity: {forecast_data.humidity}
"""

async def join_forecasts(forecasts: AsyncIterable[ForecastModel]) -> str:
    """
    Turn iterable of ForecastModel into list,
    while converting each forecast,
    then join them as a single str.
    """
    forecasts_list: list[str] = []
    async for forecast in forecasts:
        forecasts_list.append(convert_forecast(forecast))
    return "\n".join(forecasts_list)
