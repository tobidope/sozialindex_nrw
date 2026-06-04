from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT_DIR / "sozialindex_schulliste_schuljahr_2025-26.pdf"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "sozialindex.duckdb"
TABLE_NAME = "schulen"
METADATA_TABLE_NAME = "import_metadata"

COLUMNS = [
    "bezirksregierung",
    "kreis_kreisfreie_stadt",
    "schulform",
    "schulnummer",
    "schulname",
    "sozialindexstufe",
    "strasse",
    "plz",
    "ort",
    "latitude",
    "longitude",
    "geo_match_status",
]


def connect(db_path: Path = DB_PATH, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def write_schulen(
    df: pd.DataFrame,
    db_path: Path = DB_PATH,
    imported_at: datetime | None = None,
) -> None:
    imported_at = imported_at or datetime.now(timezone.utc)
    with connect(db_path, read_only=True) as con:
        con.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        con.register("schulen_df", df[COLUMNS])
        con.execute(
            f"""
            CREATE TABLE {TABLE_NAME} AS
            SELECT
                bezirksregierung::TEXT AS bezirksregierung,
                kreis_kreisfreie_stadt::TEXT AS kreis_kreisfreie_stadt,
                schulform::TEXT AS schulform,
                schulnummer::INTEGER AS schulnummer,
                schulname::TEXT AS schulname,
                sozialindexstufe::INTEGER AS sozialindexstufe,
                strasse::TEXT AS strasse,
                plz::TEXT AS plz,
                ort::TEXT AS ort,
                latitude::DOUBLE AS latitude,
                longitude::DOUBLE AS longitude,
                geo_match_status::TEXT AS geo_match_status
            FROM schulen_df
            """
        )
        con.execute(f"DROP TABLE IF EXISTS {METADATA_TABLE_NAME}")
        con.execute(
            f"""
            CREATE TABLE {METADATA_TABLE_NAME} (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        con.execute(
            f"INSERT INTO {METADATA_TABLE_NAME} VALUES (?, ?)",
            ["imported_at", imported_at.isoformat()],
        )


def read_schulen(db_path: Path = DB_PATH) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=COLUMNS)

    with connect(db_path, read_only=True) as con:
        return con.execute(
            f"""
            SELECT
                bezirksregierung,
                kreis_kreisfreie_stadt,
                schulform,
                schulnummer,
                schulname,
                sozialindexstufe,
                strasse,
                plz,
                ort,
                latitude,
                longitude,
                geo_match_status
            FROM {TABLE_NAME}
            ORDER BY
                bezirksregierung,
                kreis_kreisfreie_stadt,
                schulform,
                schulname
            """
        ).df()


def read_imported_at(db_path: Path = DB_PATH) -> datetime | None:
    if not db_path.exists():
        return None

    with connect(db_path) as con:
        metadata_exists = con.execute(
            """
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [METADATA_TABLE_NAME],
        ).fetchone()[0]
        if not metadata_exists:
            return None

        row = con.execute(
            f"SELECT value FROM {METADATA_TABLE_NAME} WHERE key = ?",
            ["imported_at"],
        ).fetchone()
        if row is None:
            return None

    return datetime.fromisoformat(row[0])
