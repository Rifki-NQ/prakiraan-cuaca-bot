from collections.abc import AsyncGenerator

import pytest_asyncio

from src.queries.sqlite_query import LocationFinder
from tests.paths import adm4_codes_csv_path, temp_local_db_path


@pytest_asyncio.fixture(scope="module")
async def location_finder() -> AsyncGenerator[LocationFinder, None]:
    db_file_url = temp_local_db_path()
    db_url = f"sqlite+aiosqlite:///{db_file_url}"
    location_finder = LocationFinder(local_db_url=db_url)
    async with location_finder:
        await location_finder.start_csv_to_local_db_transformation(
            adm4_codes_csv_path()
        )
        yield location_finder
    db_file_url.unlink()
