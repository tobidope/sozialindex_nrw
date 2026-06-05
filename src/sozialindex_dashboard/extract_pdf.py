from __future__ import annotations

import argparse
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Iterable
from urllib.request import urlretrieve

import pandas as pd
import pdfplumber
from pyproj import Transformer

from sozialindex_dashboard.config import load_source_config
from sozialindex_dashboard.db import COLUMNS, DB_PATH, PDF_PATH, write_schulen

SOCIALINDEX_COLUMNS = [
    "bezirksregierung",
    "kreis_kreisfreie_stadt",
    "schulform",
    "schulnummer",
    "schulname",
    "sozialindexstufe",
]
SCHOOL_NUMBER_RE = re.compile(r"^\d{6}$")
INDEX_RE = re.compile(r"^\d+$")
UTM32_TO_WGS84 = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
SCHOOL_BASE_COLUMN_MAP = {
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


def download_pdf(url: str, target_path: Path = PDF_PATH) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, target_path)
    return target_path


def _join_words(words: Iterable[dict]) -> str:
    return " ".join(
        word["text"] for word in sorted(words, key=lambda item: item["x0"])
    ).strip()


def _line_key(word: dict) -> int:
    return round(float(word["top"]))


def _extract_line_rows(page) -> list[dict[str, str | int]]:
    words = [
        word
        for word in page.extract_words(x_tolerance=1, y_tolerance=3)
        if 92 <= float(word["top"]) <= page.height - 35
    ]
    grouped: dict[int, list[dict]] = {}
    for word in words:
        grouped.setdefault(_line_key(word), []).append(word)

    rows: list[dict[str, str | int]] = []
    for line_words in grouped.values():
        text = _join_words(line_words)
        if not text or text.startswith(("Bezirksregierung", "Seite ")):
            continue

        number_words = [
            word for word in line_words if SCHOOL_NUMBER_RE.match(word["text"])
        ]
        index_words = [
            word
            for word in line_words
            if INDEX_RE.match(word["text"]) and float(word["x0"]) >= 470
        ]
        if not number_words or not index_words:
            continue

        number_word = min(number_words, key=lambda word: abs(float(word["x0"]) - 300))
        index_word = max(index_words, key=lambda word: float(word["x0"]))

        row = {
            "bezirksregierung": _join_words(
                word for word in line_words if 70 <= float(word["x0"]) < 130
            ),
            "kreis_kreisfreie_stadt": _join_words(
                word for word in line_words if 130 <= float(word["x0"]) < 215
            ),
            "schulform": _join_words(
                word for word in line_words if 215 <= float(word["x0"]) < 290
            ),
            "schulnummer": int(number_word["text"]),
            "schulname": _join_words(
                word for word in line_words if 330 <= float(word["x0"]) < 470
            ),
            "sozialindexstufe": int(index_word["text"]),
        }
        rows.append(row)

    return rows


def extract_pdf(pdf_path: Path = PDF_PATH) -> pd.DataFrame:
    current = {
        "bezirksregierung": "",
        "kreis_kreisfreie_stadt": "",
        "schulform": "",
    }
    records: list[dict[str, str | int]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for row in _extract_line_rows(page):
                for column in current:
                    value = str(row[column]).strip()
                    if value:
                        current[column] = value
                    row[column] = current[column]
                records.append(row)

    df = pd.DataFrame.from_records(records, columns=SOCIALINDEX_COLUMNS)
    if df.empty:
        raise RuntimeError(f"No school rows could be extracted from {pdf_path}")

    df["schulnummer"] = pd.to_numeric(df["schulnummer"], errors="raise").astype("int64")
    df["schulname"] = (
        df["schulname"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    df["sozialindexstufe"] = pd.to_numeric(
        df["sozialindexstufe"], errors="raise"
    ).astype("int64")
    df = df.dropna(subset=["schulnummer", "schulname", "sozialindexstufe"])
    df = df.drop_duplicates(subset=["schulnummer"]).reset_index(drop=True)

    missing_group_values = df[
        (df["bezirksregierung"] == "")
        | (df["kreis_kreisfreie_stadt"] == "")
        | (df["schulform"] == "")
    ]
    if not missing_group_values.empty:
        raise RuntimeError("Some rows are missing grouped values after forward-fill.")

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

    return df


def enrich_with_geodata(socialindex_df: pd.DataFrame, url: str) -> pd.DataFrame:
    base_df = _read_school_base_data(url)
    enriched_df = socialindex_df.merge(base_df, on="schulnummer", how="left")
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
        "--pdf",
        type=Path,
        help="Source PDF path. If omitted, the configured PDF URL is downloaded.",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Target DuckDB path")
    parser.add_argument(
        "--pdf-url",
        default=source_config.socialindex_pdf_url,
        help="Socialindex school list PDF URL",
    )
    parser.add_argument(
        "--school-base-data-url",
        default=source_config.school_base_data_url,
        help="Official NRW school base data CSV URL",
    )
    args = parser.parse_args()

    pdf_path = args.pdf if args.pdf is not None else download_pdf(args.pdf_url)
    df = enrich_with_geodata(extract_pdf(pdf_path), args.school_base_data_url)
    write_schulen(df, args.db, imported_at=datetime.now(timezone.utc))
    print(f"Wrote {len(df):,} schools to {args.db}")


if __name__ == "__main__":
    main()
