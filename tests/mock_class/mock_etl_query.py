from typing import Any, Mapping, cast
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import Row
from tests.mock_data.mock_db_data import MOCK_WEATHER_FORECAST_DATA


@dataclass
class FakeRow:
    _mapping: Mapping[str, Any]


async def fake_rows(fake_mapped_rows: list[dict[str, Any]]) -> AsyncIterable[FakeRow]:
    for fake_mapped_row in fake_mapped_rows:
        yield FakeRow(_mapping=fake_mapped_row)


class MockETLQuery:
    async def get_forecast_by_range(
        self, adm4_code: str, datetime_range: tuple[datetime, datetime]
    ) -> AsyncIterable[Row[Any]]:
        return cast(AsyncIterable[Row[Any]], fake_rows(MOCK_WEATHER_FORECAST_DATA))
