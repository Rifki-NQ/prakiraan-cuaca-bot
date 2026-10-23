from collections.abc import AsyncGenerator

import pytest_asyncio

from src.queries.sqlite_query import LocationFinder
from tests.paths import adm4_codes_csv_path, temp_local_db_path


@pytest_asyncio.fixture(scope="module")
async def location_finder() -> AsyncGenerator[LocationFinder, None]:
    location_finder = LocationFinder()
    db_file_url = temp_local_db_path()
    db_url = f"sqlite+aiosqlite:///{db_file_url}"
    await location_finder.setup_local_db(db_url)
    await location_finder.start_csv_to_local_db_transformation(adm4_codes_csv_path())
    yield location_finder
    await location_finder._get_local_db().engine.dispose()  # pyright: ignore[reportPrivateUsage]
    db_file_url.unlink()
