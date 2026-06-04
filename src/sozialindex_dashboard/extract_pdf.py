from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import pdfplumber

from sozialindex_dashboard.db import COLUMNS, DB_PATH, PDF_PATH, write_schulen

SCHOOL_NUMBER_RE = re.compile(r"^\d{6}$")
INDEX_RE = re.compile(r"^\d+$")


def _join_words(words: Iterable[dict]) -> str:
    return " ".join(word["text"] for word in sorted(words, key=lambda item: item["x0"])).strip()


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

        number_words = [word for word in line_words if SCHOOL_NUMBER_RE.match(word["text"])]
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
            "schulnummer": number_word["text"].strip(),
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

    df = pd.DataFrame.from_records(records, columns=COLUMNS)
    if df.empty:
        raise RuntimeError(f"No school rows could be extracted from {pdf_path}")

    df["schulnummer"] = df["schulnummer"].astype("string").str.strip()
    df["schulname"] = df["schulname"].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    df["sozialindexstufe"] = pd.to_numeric(df["sozialindexstufe"], errors="raise").astype("int64")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract NRW Sozialindex school data into DuckDB.")
    parser.add_argument("--pdf", type=Path, default=PDF_PATH, help="Source PDF path")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Target DuckDB path")
    args = parser.parse_args()

    df = extract_pdf(args.pdf)
    write_schulen(df, args.db)
    print(f"Wrote {len(df):,} schools to {args.db}")


if __name__ == "__main__":
    main()
