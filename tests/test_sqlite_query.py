import pytest
import pytest_asyncio
import csv
import logging
from collections.abc import AsyncGenerator
from sqlalchemy import inspect, select, func, Connection, Table
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.paths import temp_local_db_path, adm4_codes_csv_path
from tests.tests_utils import get_tables_name
from src.queries.sqlite_query import LocationFinder
from src.models.contexts import LocalDBContext
from src.exceptions import EmptyQueryResultError, DBNotInitializedError


@pytest_asyncio.fixture(scope="module")
async def location_finder() -> AsyncGenerator[LocationFinder, None]:
    location_finder = LocationFinder()
    db_file_url = temp_local_db_path()
    db_url = f"sqlite+aiosqlite:///{db_file_url}"
    await location_finder.setup_local_db(db_url)
    yield location_finder
    await location_finder._get_local_db().engine.dispose()  # pyright: ignore[reportPrivateUsage]
    db_file_url.unlink()


async def test_second_setup_local_db(
    location_finder: LocationFinder, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    await location_finder.setup_local_db("")
    assert "already called" in caplog.messages[0]


async def test_get_local_db_without_setup_first() -> None:
    location_finder = LocationFinder()
    with pytest.raises(DBNotInitializedError):
        location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]


async def test_local_db_attributes_after_setup_local_db(
    location_finder: LocationFinder,
) -> None:
    # setup_local_db() is already called in the location_finder fixture
    local_db = location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]
    assert local_db is not None
    assert isinstance(local_db, LocalDBContext)
    assert isinstance(local_db.engine, AsyncEngine)
    assert isinstance(local_db.location_table, Table)
    assert local_db.location_table.name == "forecast_location"


async def test_setup_local_db_create_table_in_db(
    location_finder: LocationFinder,
) -> None:
    # setup_local_db() is already called in the location_finder fixture
    local_db = location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]
    table_names_from_db = await get_tables_name(local_db.engine)
    assert local_db.location_table.name in table_names_from_db


async def test_start_csv_to_local_db_transformation_db_file_created(
    location_finder: LocationFinder,
) -> None:
    adm4_codes_csv_filepath = adm4_codes_csv_path()
    # start the transformation from csv to db
    await location_finder.start_csv_to_local_db_transformation(adm4_codes_csv_filepath)
    assert adm4_codes_csv_filepath.exists()


async def test_start_csv_to_local_db_transformation_table_exists(
    location_finder: LocationFinder,
) -> None:
    db = location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]

    def _tables_name_inspector(sync_conn: Connection) -> list[str]:
        return inspect(sync_conn).get_table_names()

    async with db.engine.connect() as conn:
        tables_name = await conn.run_sync(_tables_name_inspector)
    assert db.location_table.name in tables_name


async def test_start_csv_to_local_db_transformation_columns_exist(
    location_finder: LocationFinder,
) -> None:
    db = location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]

    def _columns_name_inspector(sync_conn: Connection) -> list[str]:
        return [
            col["name"] for col in inspect(sync_conn).get_columns("forecast_location")
        ]

    async with db.engine.connect() as conn:
        columns_name = await conn.run_sync(_columns_name_inspector)
    expected = set(db.location_table.c.keys())
    actual = set(columns_name)
    assert expected == actual, (
        f"missing: {expected - actual}, unexpected: {actual - expected}"
    )


async def test_start_csv_to_local_db_transformation_rows_count(
    location_finder: LocationFinder,
) -> None:
    adm4_codes_csv_filepath = adm4_codes_csv_path()
    db = location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]

    with open(adm4_codes_csv_filepath, mode="r", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        csv_row_count = sum(1 for _ in reader)

    async with db.engine.connect() as conn:
        stmt = select(func.count()).select_from(db.location_table)
        db_row_count = (await conn.execute(stmt)).scalar()

    assert csv_row_count == db_row_count


async def test_start_csv_to_local_db_transformation_single_row_value(
    location_finder: LocationFinder,
) -> None:
    adm4_codes_csv_filepath = adm4_codes_csv_path()
    db = location_finder._get_local_db()  # pyright: ignore[reportPrivateUsage]

    with open(adm4_codes_csv_filepath, mode="r", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip the header part
        csv_first_value = next(reader)
        # making sure we're testing the same row with the db
        assert csv_first_value[0] == "32.01.01.1001"

    async with db.engine.connect() as conn:
        stmt = select(db.location_table).where(
            db.location_table.c.kode_adm4 == "32.01.01.1001"
        )
        db_selected_row = (await conn.execute(stmt)).one()

    expected = set(
        [v.lower() for v in csv_first_value]
    )  # match the db lowered values in transformation process
    expected.discard(
        "jawa barat"
    )  # discard the value from province column since the transformation also removes it
    actual = set(db_selected_row)
    assert expected == actual, (
        f"missing: {expected - actual}, unexpected: {actual - expected}"
    )


async def test_search_city_or_regency_by_exact_name(
    location_finder: LocationFinder,
) -> None:
    results = await location_finder.search_city_or_regency("kabupaten bekasi")
    assert len(results) == 1
    assert results[0] == "kabupaten bekasi"


async def test_search_city_or_regency_by_partial_name(
    location_finder: LocationFinder,
) -> None:
    results = await location_finder.search_city_or_regency("bekasi")
    assert len(results) == 2
    assert "kabupaten bekasi" in results
    assert "kota bekasi" in results


async def test_search_city_or_regency_by_non_existent_name_pattern(
    location_finder: LocationFinder,
) -> None:
    with pytest.raises(EmptyQueryResultError) as exc_info:
        await location_finder.search_city_or_regency("bkasi")
    assert exc_info.value.query.get("city_or_regency") == "bkasi"


async def test_search_subdistrict_by_exact_name(
    location_finder: LocationFinder,
) -> None:
    results = await location_finder.search_subdistrict("kabupaten bekasi")
    assert len(results) == 23
    assert "tarumajaya" in results
    assert "babelan" in results
    assert "sukawangi" in results
    assert "tambelang" in results
    assert "tambun utara" in results
    assert "tambun selatan" in results
    assert "cibitung" in results
    assert "cikarang barat" in results
    assert "cikarang utara" in results
    assert "karang bahagia" in results
    assert "cikarang timur" in results
    assert "kedung waringin" in results
    assert "pebayuran" in results
    assert "sukakarya" in results
    assert "sukatani" in results
    assert "cabangbungin" in results
    assert "muaragembong" in results
    assert "setu" in results
    assert "cikarang selatan" in results
    assert "cikarang pusat" in results
    assert "serang baru" in results
    assert "cibarusah" in results
    assert "bojongmangu" in results


async def test_search_subdistrict_by_partial_name(
    location_finder: LocationFinder,
) -> None:
    """
    Test that EmptyQueryResultError is raised, since search_subdistrict()
    requires the exact name of the 'city_or_regency'.
    """
    with pytest.raises(EmptyQueryResultError) as exc_info:
        await location_finder.search_subdistrict("bekasi")
    assert exc_info.value.query.get("city_or_regency") == "bekasi"


async def test_search_village_by_exact_names(location_finder: LocationFinder) -> None:
    results = await location_finder.search_village("kabupaten bekasi", "cikarang pusat")
    assert len(results) == 6
    assert "cicau" in results
    assert "sukamahi" in results
    assert "pasiranji" in results
    assert "hegarmukti" in results
    assert "jayamukti" in results
    assert "pasirtanjung" in results


async def test_search_village_by_partial_subdistrict_name(
    location_finder: LocationFinder,
) -> None:
    """
    Test that EmptyQueryResultError is raised, since search_village()
    requires both the exact names of 'city_or_regency' and 'subdistrict'.
    """
    with pytest.raises(EmptyQueryResultError) as exc_info:
        await location_finder.search_village("kabupaten bekasi", "cikarang")
    assert exc_info.value.query.get("city_or_regency") == "kabupaten bekasi"
    assert exc_info.value.query.get("subdistrict") == "cikarang"


async def test_get_adm4_code_by_exact_adress(location_finder: LocationFinder) -> None:
    result = await location_finder.get_adm4_code(
        "kabupaten bekasi", "cikarang pusat", "sukamahi"
    )
    assert "32.16.20.2002" == result


async def test_get_adm4_code_by_non_exact_village_name(
    location_finder: LocationFinder,
) -> None:
    """
    Test that EmptyQueryResultError is raised, since get_adm4_code()
    requires the exact adress name, which mean the exact names for all
    'city_or_regency', 'subdistrict' and 'village'.
    """
    with pytest.raises(EmptyQueryResultError) as exc_info:
        await location_finder.get_adm4_code(
            "kabupaten bekasi", "cikarang pusat", "sukamah"
        )
    assert exc_info.value.query.get("city_or_regency") == "kabupaten bekasi"
    assert exc_info.value.query.get("subdistrict") == "cikarang pusat"
    assert exc_info.value.query.get("village") == "sukamah"


async def test_get_full_address_return_expected(
    location_finder: LocationFinder,
) -> None:
    address = await location_finder.get_full_address("32.16.20.2003")
    assert address.kabupaten_atau_kota == "kabupaten bekasi"
    assert address.kecamatan == "cikarang pusat"
    assert address.desa_atau_kelurahan == "pasiranji"


async def test_get_full_address_by_invalid_adm4_code(
    location_finder: LocationFinder,
) -> None:
    with pytest.raises(EmptyQueryResultError) as exc_info:
        await location_finder.get_full_address("invalid_code")
    assert exc_info.value.query.get("adm4_code") == "invalid_code"


@pytest.mark.parametrize(
    "input_value, expected_return",
    [
        ("%", "\\%"),
        ("_", "\\_"),
        ("\\", "\\\\"),
        ("%%", "\\%\\%"),
        ("__", "\\_\\_"),
        ("\\\\", "\\\\\\\\"),
    ],
)
def test_escape_string_return_expected(
    location_finder: LocationFinder, input_value: str, expected_return: str
) -> None:
    assert (
        location_finder._escape_string(input_value)  # pyright: ignore[reportPrivateUsage]
        == expected_return
    )
