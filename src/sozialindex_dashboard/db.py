from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
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
    "schuldaten_schulform",
    "schulbezeichnung_1",
    "schulbezeichnung_2",
    "schulbezeichnung_3",
    "kurzbezeichnung",
    "schuldaten_bezirksregierung",
    "telefonvorwahl",
    "telefon",
    "faxvorwahl",
    "fax",
    "email",
    "homepage",
    "rechtsform",
    "traegernummer",
    "gemeindeschluessel",
    "schulbetriebsschluessel",
    "schulbetriebsdatum",
    "epsg",
    "utm_rechtswert",
    "utm_hochwert",
]

FILTER_OPTION_COLUMNS = [
    "bezirksregierung",
    "kreis_kreisfreie_stadt",
    "schulform",
    "sozialindexstufe",
]


def _distance_expression() -> str:
    """Return a SQL Haversine expression for distance in kilometers.

    The placeholders expect origin latitude, origin latitude again, and origin
    longitude. The destination coordinates are read from the table columns
    latitude and longitude.
    """
    return """
        6371.0088 * 2 * asin(
            sqrt(
                pow(sin((radians(latitude) - radians(?)) / 2), 2)
                + cos(radians(?))
                * cos(radians(latitude))
                * pow(sin((radians(longitude) - radians(?)) / 2), 2)
            )
        )
    """


def _build_filtered_query(
    *,
    query: str,
    bezirksregierungen: list[str],
    kreise: list[str],
    schulformen: list[str],
    sozialindexstufen: list[int],
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int | None = None,
) -> tuple[str, list[Any]]:
    select_fields = "*"
    params: list[Any] = []
    clauses: list[str] = []
    distance_expr = None

    if latitude is not None and longitude is not None:
        distance_expr = _distance_expression()
        select_fields = f"*, {distance_expr} AS entfernung_km"
        params.extend([latitude, latitude, longitude])

    if query:
        clauses.append(
            """
            contains(
                lower(
                    coalesce(kurzbezeichnung, '')
                    || ' '
                    || coalesce(schulname, '')
                    || ' '
                    || cast(schulnummer AS VARCHAR)
                ),
                lower(?)
            )
            """
        )
        params.append(query)

    if bezirksregierungen:
        clauses.append("bezirksregierung IN ?")
        params.append(bezirksregierungen)
    if kreise:
        clauses.append("kreis_kreisfreie_stadt IN ?")
        params.append(kreise)
    if schulformen:
        clauses.append("schulform IN ?")
        params.append(schulformen)
    if sozialindexstufen:
        clauses.append("sozialindexstufe IN ?")
        params.append(sozialindexstufen)

    if distance_expr is not None and radius_km is not None:
        clauses.append("latitude IS NOT NULL AND longitude IS NOT NULL")
        clauses.append(f"{distance_expr} <= ?")
        params.extend([latitude, latitude, longitude, radius_km])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT {select_fields}
        FROM {TABLE_NAME}
        {where_sql}
    """
    return sql, params


def connect(
    db_path: Path = DB_PATH, read_only: bool = False
) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def write_schulen(
    df: pd.DataFrame,
    db_path: Path = DB_PATH,
    imported_at: datetime | None = None,
) -> None:
    imported_at = imported_at or datetime.now(timezone.utc)
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
                geo_match_status::TEXT AS geo_match_status,
                schuldaten_schulform::TEXT AS schuldaten_schulform,
                schulbezeichnung_1::TEXT AS schulbezeichnung_1,
                schulbezeichnung_2::TEXT AS schulbezeichnung_2,
                schulbezeichnung_3::TEXT AS schulbezeichnung_3,
                kurzbezeichnung::TEXT AS kurzbezeichnung,
                schuldaten_bezirksregierung::TEXT AS schuldaten_bezirksregierung,
                telefonvorwahl::TEXT AS telefonvorwahl,
                telefon::TEXT AS telefon,
                faxvorwahl::TEXT AS faxvorwahl,
                fax::TEXT AS fax,
                email::TEXT AS email,
                homepage::TEXT AS homepage,
                rechtsform::TEXT AS rechtsform,
                traegernummer::TEXT AS traegernummer,
                gemeindeschluessel::TEXT AS gemeindeschluessel,
                schulbetriebsschluessel::TEXT AS schulbetriebsschluessel,
                schulbetriebsdatum::TEXT AS schulbetriebsdatum,
                epsg::TEXT AS epsg,
                utm_rechtswert::DOUBLE AS utm_rechtswert,
                utm_hochwert::DOUBLE AS utm_hochwert
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
                *
            FROM {TABLE_NAME}
            ORDER BY
                bezirksregierung,
                kreis_kreisfreie_stadt,
                schulform,
                schulname
            """
        ).df()


def read_filter_options(db_path: Path = DB_PATH) -> dict[str, list]:
    if not db_path.exists():
        return {column: [] for column in FILTER_OPTION_COLUMNS}

    options = {}
    with connect(db_path, read_only=True) as con:
        for column in FILTER_OPTION_COLUMNS:
            rows = con.execute(
                f"""
                SELECT DISTINCT {column}
                FROM {TABLE_NAME}
                WHERE {column} IS NOT NULL
                ORDER BY {column}
                """
            ).fetchall()
            options[column] = [row[0] for row in rows]
    return options


def query_schulen(
    *,
    query: str,
    bezirksregierungen: list[str],
    kreise: list[str],
    schulformen: list[str],
    sozialindexstufen: list[int],
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int | None = None,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame(columns=COLUMNS)

    sql, params = _build_filtered_query(
        query=query,
        bezirksregierungen=bezirksregierungen,
        kreise=kreise,
        schulformen=schulformen,
        sozialindexstufen=sozialindexstufen,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    order_sql = (
        "ORDER BY entfernung_km, bezirksregierung, kreis_kreisfreie_stadt, schulform, schulname"
        if latitude is not None and longitude is not None
        else "ORDER BY bezirksregierung, kreis_kreisfreie_stadt, schulform, schulname"
    )

    with connect(db_path, read_only=True) as con:
        return con.execute(f"{sql} {order_sql}", params).df()


def read_summary(
    *,
    query: str,
    bezirksregierungen: list[str],
    kreise: list[str],
    schulformen: list[str],
    sozialindexstufen: list[int],
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int | None = None,
    db_path: Path = DB_PATH,
) -> dict[str, int | float | None]:
    if not db_path.exists():
        return {
            "schulen": 0,
            "kreise": 0,
            "schulformen": 0,
            "durchschnitt_sozialindex": None,
            "mit_koordinaten": 0,
        }

    sql, params = _build_filtered_query(
        query=query,
        bezirksregierungen=bezirksregierungen,
        kreise=kreise,
        schulformen=schulformen,
        sozialindexstufen=sozialindexstufen,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    with connect(db_path, read_only=True) as con:
        row = con.execute(
            f"""
            SELECT
                count(*) AS schulen,
                count(DISTINCT kreis_kreisfreie_stadt) AS kreise,
                count(DISTINCT schulform) AS schulformen,
                avg(sozialindexstufe) AS durchschnitt_sozialindex,
                count(latitude) AS mit_koordinaten
            FROM ({sql}) filtered
            """,
            params,
        ).fetchone()

    return {
        "schulen": row[0],
        "kreise": row[1],
        "schulformen": row[2],
        "durchschnitt_sozialindex": row[3],
        "mit_koordinaten": row[4],
    }


def read_sozialindex_counts(
    *,
    query: str,
    bezirksregierungen: list[str],
    kreise: list[str],
    schulformen: list[str],
    sozialindexstufen: list[int],
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int | None = None,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    sql, params = _build_filtered_query(
        query=query,
        bezirksregierungen=bezirksregierungen,
        kreise=kreise,
        schulformen=schulformen,
        sozialindexstufen=sozialindexstufen,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    with connect(db_path, read_only=True) as con:
        return con.execute(
            f"""
            SELECT sozialindexstufe, count(*) AS "Anzahl Schulen"
            FROM ({sql}) filtered
            GROUP BY sozialindexstufe
            ORDER BY sozialindexstufe
            """,
            params,
        ).df()


def read_schulform_counts(
    *,
    query: str,
    bezirksregierungen: list[str],
    kreise: list[str],
    schulformen: list[str],
    sozialindexstufen: list[int],
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: int | None = None,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    sql, params = _build_filtered_query(
        query=query,
        bezirksregierungen=bezirksregierungen,
        kreise=kreise,
        schulformen=schulformen,
        sozialindexstufen=sozialindexstufen,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
    with connect(db_path, read_only=True) as con:
        return con.execute(
            f"""
            SELECT schulform, count(*) AS "Anzahl Schulen"
            FROM ({sql}) filtered
            GROUP BY schulform
            ORDER BY "Anzahl Schulen" DESC
            """,
            params,
        ).df()


def read_imported_at(db_path: Path = DB_PATH) -> datetime | None:
    if not db_path.exists():
        return None

    with connect(db_path, read_only=True) as con:
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
