from collections.abc import AsyncIterable
from src.models.protocols import AppServiceProtocol
from src.models.commands import Commands
from src.models.domain_model import ForecastModel


class CommandRouter:
    def __init__(self, app_service: AppServiceProtocol) -> None:
        self.app_service = app_service

    def route_command(self, command: Commands) -> AsyncIterable[ForecastModel]:
        if command == Commands.TODAY:
            return self.app_service.get_today_weather_forecast()
        elif command == Commands.TOMORROW:
            return self.app_service.get_tomorrow_weather_forecast()
