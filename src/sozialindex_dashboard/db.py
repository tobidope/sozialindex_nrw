from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT_DIR / "sozialindex_schulliste_schuljahr_2025-26.pdf"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "sozialindex.duckdb"
TABLE_NAME = "schulen"

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


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def write_schulen(df: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    with connect(db_path) as con:
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


def read_schulen(db_path: Path = DB_PATH) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=COLUMNS)

    with connect(db_path) as con:
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
