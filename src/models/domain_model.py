from dataclasses import dataclass, asdict
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
class UserDataModel:
    chat_id: int
    username: str | None
    adm4_code: str


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
