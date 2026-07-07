import pytest
from unittest.mock import MagicMock
from datetime import datetime
from src.query import QueryBuilder
from src.exceptions import InvalidDatetimeRangeError


@pytest.mark.parametrize("start_dt", [datetime(2020, 2, 2), datetime(2020, 2, 3)])
async def test_invalid_datetime_range(start_dt: datetime) -> None:
    end_dt = datetime(2020, 2, 2)
    obj = QueryBuilder(MagicMock(), MagicMock())
    datetime_range = (start_dt, end_dt)
    with pytest.raises(InvalidDatetimeRangeError) as exc_info:
        await obj.get_forecast_by_range(datetime_range)
    assert exc_info.value.start_dt == start_dt
    assert exc_info.value.end_dt == end_dt
