from src.models.enums import Commands, BotAction, UserLocationState
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class ForecastModel:
    forecast_datetime: datetime  # datetime for the weather forecast
    analysis_datetime: datetime  # datetime for the forecast analysis
    adm4_code: str  # district level four code, the forecast location
    temperature: int  # temperature in celcius
    total_cloud_coverage: int  # percentage unit
    total_precipitation: float  # mm unit
    weather_description: str
    weather_description_eng: str
    wind_direction_degree: int
    wind_direction_compass: str  # direction from
    wind_direction_compass_to: str  # direction to
    wind_speed: float  # km/h unit
    humidity: int  # percentage
    visibility: int  # meters unit
    updated_at: datetime  # datetime for the forecast last update
    created_at: datetime  # datetime for the forecast creation


@dataclass
class DatetimeModel:
    """
    Automatically fills non init attribute from current_datetime

    non init fields:
        current_datetime_start: datetime = replace current_datetime time to 00:00:00
        current_datetime_end: datetime = replace current_datetime time to 23:59:59
    """

    current_datetime: datetime
    current_datetime_start: datetime = field(init=False)
    current_datetime_end: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.current_datetime = self.current_datetime.replace(tzinfo=None)
        self.current_datetime_start = self.current_datetime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.current_datetime_end = self.current_datetime.replace(
            hour=23, minute=59, second=59, microsecond=0
        )


@dataclass
class BotUserModel:
    chat_id: int
    username: str | None = None
    adm4_code: str | None = None


@dataclass
class BotUserStateModel:
    chat_id: int
    kabupaten_atau_kota: str | None = None
    kecamatan: str | None = None
    desa_atau_kelurahan: str | None = None


@dataclass
class CSVLocationDataModel:
    kode_adm4: str
    kabupaten_atau_kota: str
    kecamatan: str
    desa_atau_kelurahan: str

    def __post_init__(self) -> None:
        self.kabupaten_atau_kota = self.kabupaten_atau_kota.lower()
        self.kecamatan = self.kecamatan.lower()
        self.desa_atau_kelurahan = self.desa_atau_kelurahan.lower()

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class LocationFlowResult:
    message: str
    bot_user_state: BotUserStateModel | None = None


@dataclass
class LocationFlowResultComplete:
    message: str
    bot_user_state: BotUserStateModel
    adm4_code: str


@dataclass(frozen=True)
class ActionEntry:
    command: Commands
    # None in user_state means this bot_action does not care
    # whether this user has user_state or not
    user_state: UserLocationState | None
    need_input_value: bool
    bot_action: tuple[BotAction, ...]
