from pathlib import Path

TEST_DIR = Path(__file__).parent
TEMP_TEST_DIR = TEST_DIR / "temp"


def temp_local_db_path(db_file_name: str = "temp_database.db") -> Path:
    return TEMP_TEST_DIR / db_file_name


def adm4_codes_csv_path() -> Path:
    return TEST_DIR.parent / "adm4_codes" / "jawa_barat.csv"
