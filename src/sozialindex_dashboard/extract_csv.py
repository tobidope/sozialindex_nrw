from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd
from pyproj import Transformer

from sozialindex_dashboard.config import load_source_config
from sozialindex_dashboard.db import COLUMNS, DATA_DIR, DB_PATH, write_schulen

SOCIALINDEX_CSV_PATH: Path = DATA_DIR / "schulliste_sj_25_26_open_data.csv"
SOCIALINDEX_COLUMNS: tuple[str, ...] = (
    "bezirksregierung",
    "kreis_kreisfreie_stadt",
    "schulnummer",
    "schulname",
    "sozialindexstufe",
)
SOCIALINDEX_COLUMN_MAP: dict[str, str] = {
    "Schulnummer": "schulnummer",
    "Kurzbezeichnung": "schulname",
    "Bezirksregierung": "bezirksregierung",
    "Kreis": "kreis_kreisfreie_stadt",
    "Sozialindexstufe": "sozialindexstufe",
}
UTM32_TO_WGS84 = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
NRW_LATITUDE_RANGE = (50.0, 53.0)
NRW_LONGITUDE_RANGE = (5.0, 10.0)
SCHOOL_BASE_COLUMN_MAP: dict[str, str] = {
    "Schulnummer": "schulnummer",
    "Schulform": "schuldaten_schulform",
    "Schulbezeichnung_1": "schulbezeichnung_1",
    "Schulbezeichnung_2": "schulbezeichnung_2",
    "Schulbezeichnung_3": "schulbezeichnung_3",
    "Kurzbezeichnung": "kurzbezeichnung",
    "Bezirksregierung": "schuldaten_bezirksregierung",
    "PLZ": "plz",
    "Ort": "ort",
    "Strasse": "strasse",
    "Telefonvorwahl": "telefonvorwahl",
    "Telefon": "telefon",
    "Faxvorwahl": "faxvorwahl",
    "Fax": "fax",
    "E-Mail": "email",
    "Homepage": "homepage",
    "Rechtsform": "rechtsform",
    "Traegernummer": "traegernummer",
    "Gemeindeschluessel": "gemeindeschluessel",
    "Schulbetriebsschluessel": "schulbetriebsschluessel",
    "Schulbetriebsdatum": "schulbetriebsdatum",
    "EPSG": "epsg",
    "UTMRechtswert": "utm_rechtswert",
    "UTMHochwert": "utm_hochwert",
}


def download_csv(url: str, target_path: Path = SOCIALINDEX_CSV_PATH) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, target_path)
    return target_path


def extract_csv(csv_path: Path = SOCIALINDEX_CSV_PATH) -> pd.DataFrame:
    raw_df = pd.read_csv(csv_path, sep=";", encoding="cp850", dtype="string")
    missing_columns = sorted(set(SOCIALINDEX_COLUMN_MAP) - set(raw_df.columns))
    if missing_columns:
        raise RuntimeError(
            "The socialindex CSV is missing required columns: "
            + ", ".join(missing_columns)
        )

    df = raw_df[list(SOCIALINDEX_COLUMN_MAP)].rename(columns=SOCIALINDEX_COLUMN_MAP)
    df["schulnummer"] = pd.to_numeric(df["schulnummer"], errors="raise").astype("int64")
    df["schulname"] = (
        df["schulname"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    for column in ["bezirksregierung", "kreis_kreisfreie_stadt"]:
        df[column] = df[column].astype("string").str.strip()

    df["sozialindexstufe"] = pd.to_numeric(df["sozialindexstufe"], errors="coerce")
    df = df.dropna(subset=["schulnummer", "schulname", "sozialindexstufe"])
    df["sozialindexstufe"] = df["sozialindexstufe"].astype("int64")
    df = df[list(SOCIALINDEX_COLUMNS)]

    if df.empty:
        raise RuntimeError(f"No school rows could be extracted from {csv_path}")

    df = df.drop_duplicates(subset=["schulnummer"]).reset_index(drop=True)

    missing_group_values = df[
        (df["bezirksregierung"] == "")
        | (df["kreis_kreisfreie_stadt"] == "")
    ]
    if not missing_group_values.empty:
        raise RuntimeError("Some rows are missing required group values.")

    return df


def _normalize_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce").astype("Float64")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce").astype("Float64")

    valid_coordinates = df["latitude"].between(*NRW_LATITUDE_RANGE) & df[
        "longitude"
    ].between(*NRW_LONGITUDE_RANGE)
    df.loc[~valid_coordinates, ["latitude", "longitude"]] = pd.NA
    return df


def _read_school_base_data(url: str) -> pd.DataFrame:
    raw_df = pd.read_csv(
        url,
        sep=";",
        encoding="utf-8",
        skiprows=1,
        dtype={
            "PLZ": "string",
            "Telefonvorwahl": "string",
            "Telefon": "string",
            "Faxvorwahl": "string",
            "Fax": "string",
        },
    )
    required_columns = {
        "Schulnummer",
        "PLZ",
        "Ort",
        "Strasse",
        "EPSG",
        "UTMRechtswert",
        "UTMHochwert",
    }
    missing_columns = sorted(required_columns - set(raw_df.columns))
    if missing_columns:
        raise RuntimeError(
            "The school base data CSV is missing required columns: "
            + ", ".join(missing_columns)
        )

    df = raw_df[list(SCHOOL_BASE_COLUMN_MAP)].rename(columns=SCHOOL_BASE_COLUMN_MAP)
    df["schulnummer"] = pd.to_numeric(df["schulnummer"], errors="raise").astype("int64")
    df["utm_rechtswert"] = pd.to_numeric(df["utm_rechtswert"], errors="coerce")
    df["utm_hochwert"] = pd.to_numeric(df["utm_hochwert"], errors="coerce")

    for column in df.columns:
        if column not in {"schulnummer", "utm_rechtswert", "utm_hochwert"}:
            df[column] = df[column].astype("string").str.strip()

    epsg = df["epsg"].astype("string").str.upper().str.strip()
    has_utm_values = df["utm_rechtswert"].notna() & df["utm_hochwert"].notna()
    has_utm32 = (epsg.eq("EPSG:25832") | epsg.isna() | epsg.eq("")) & has_utm_values
    df["latitude"] = pd.NA
    df["longitude"] = pd.NA
    if has_utm32.any():
        longitudes, latitudes = UTM32_TO_WGS84.transform(
            df.loc[has_utm32, "utm_rechtswert"].to_numpy(),
            df.loc[has_utm32, "utm_hochwert"].to_numpy(),
        )
        df.loc[has_utm32, "longitude"] = longitudes
        df.loc[has_utm32, "latitude"] = latitudes

    return _normalize_coordinates(df)


def enrich_with_geodata(socialindex_df: pd.DataFrame, url: str) -> pd.DataFrame:
    base_df = _read_school_base_data(url)
    enriched_df = socialindex_df.merge(base_df, on="schulnummer", how="left")
    enriched_df["schulform"] = enriched_df["schuldaten_schulform"]
    has_coordinates = enriched_df["latitude"].notna() & enriched_df["longitude"].notna()
    enriched_df["geo_match_status"] = "missing_location"
    enriched_df.loc[has_coordinates, "geo_match_status"] = "matched"
    return enriched_df[COLUMNS]


def main() -> None:
    source_config = load_source_config()
    parser = argparse.ArgumentParser(
        description="Extract NRW Sozialindex school data into DuckDB."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Source CSV path. If omitted, the configured CSV URL is downloaded.",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Target DuckDB path")
    parser.add_argument(
        "--csv-url",
        default=source_config.socialindex_csv_url,
        help="Socialindex school list CSV URL",
    )
    parser.add_argument(
        "--school-base-data-url",
        default=source_config.school_base_data_url,
        help="Official NRW school base data CSV URL",
    )
    args = parser.parse_args()

    csv_path = args.csv if args.csv is not None else download_csv(args.csv_url)
    df = enrich_with_geodata(extract_csv(csv_path), args.school_base_data_url)
    write_schulen(df, args.db, imported_at=datetime.now(timezone.utc))
    print(f"Wrote {len(df):,} schools to {args.db}")


if __name__ == "__main__":
    main()
