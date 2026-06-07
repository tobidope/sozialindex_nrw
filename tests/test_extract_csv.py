from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "import_socialindex_csv.py"
)
spec = importlib.util.spec_from_file_location("import_socialindex_csv", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
import_socialindex_csv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(import_socialindex_csv)

enrich_with_geodata = import_socialindex_csv.enrich_with_geodata
_read_school_base_data = import_socialindex_csv._read_school_base_data
_read_student_counts = import_socialindex_csv._read_student_counts
extract_csv = import_socialindex_csv.extract_csv


def test_extract_csv_reads_cp850_and_skips_rows_without_index(tmp_path):
    csv_path = tmp_path / "schulliste.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Schulnummer;Kurzbezeichnung;Bezirksregierung;Kreis;Gemeinde;Sozialindexstufe",
                "100011;Haan, GE Walder Straße;BR Düsseldorf;Kreis Mettmann;Haan;4",
                "100218;Köln, GG Friedrich-Karl-Straße;BR Köln;Stadt Köln;Köln;ohne",
            ]
        ),
        encoding="cp850",
    )

    result = extract_csv(csv_path)

    assert result.to_dict("records") == [
        {
            "bezirksregierung": "BR Düsseldorf",
            "kreis_kreisfreie_stadt": "Kreis Mettmann",
            "schulnummer": 100011,
            "schulname": "Haan, GE Walder Straße",
            "sozialindexstufe": 4,
        }
    ]


def test_school_base_data_coordinates_are_validated_and_stored_as_floats(tmp_path):
    csv_path = tmp_path / "schuldaten.csv"
    csv_path.write_text(
        "\n".join(
            [
                "metadata row skipped by import",
                (
                    "Schulnummer;Schulform;Schulbezeichnung_1;Schulbezeichnung_2;"
                    "Schulbezeichnung_3;Kurzbezeichnung;Bezirksregierung;PLZ;Ort;"
                    "Strasse;Telefonvorwahl;Telefon;Faxvorwahl;Fax;E-Mail;Homepage;"
                    "Rechtsform;Traegernummer;Gemeindeschluessel;"
                    "Schulbetriebsschluessel;Schulbetriebsdatum;EPSG;UTMRechtswert;"
                    "UTMHochwert"
                ),
                (
                    "100001;Grundschule;Schule A;;;Schule A;Koeln;50000;Koeln;"
                    "Str. 1;0221;123;;;a@example.test;https://a.example.test;"
                    "1;10;1000;1;01.01.2020;EPSG:25832;350000;5650000"
                ),
                (
                    "100002;Grundschule;Schule B;;;Schule B;Koeln;50000;Koeln;"
                    "Str. 2;0221;456;;;b@example.test;https://b.example.test;"
                    "1;10;1000;1;01.01.2020;EPSG:25832;0;0"
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = _read_school_base_data(str(csv_path))

    assert pd.api.types.is_float_dtype(result["latitude"])
    assert pd.api.types.is_float_dtype(result["longitude"])
    assert result.loc[result["schulnummer"] == 100001, "latitude"].notna().all()
    assert result.loc[result["schulnummer"] == 100001, "longitude"].notna().all()
    assert result.loc[result["schulnummer"] == 100002, "latitude"].isna().all()
    assert result.loc[result["schulnummer"] == 100002, "longitude"].isna().all()


def test_enrich_with_geodata_maps_school_form_codes_to_labels(tmp_path):
    base_data_path = tmp_path / "schuldaten.csv"
    student_counts_path = tmp_path / "schueler.csv"
    base_data_path.write_text(
        "\n".join(
            [
                "metadata row skipped by import",
                (
                    "Schulnummer;Schulform;Schulbezeichnung_1;Schulbezeichnung_2;"
                    "Schulbezeichnung_3;Kurzbezeichnung;Bezirksregierung;PLZ;Ort;"
                    "Strasse;Telefonvorwahl;Telefon;Faxvorwahl;Fax;E-Mail;Homepage;"
                    "Rechtsform;Traegernummer;Gemeindeschluessel;"
                    "Schulbetriebsschluessel;Schulbetriebsdatum;EPSG;UTMRechtswert;"
                    "UTMHochwert"
                ),
                (
                    "100001;02;Schule A;;;Schule A;Koeln;50000;Koeln;"
                    "Str. 1;0221;123;;;a@example.test;https://a.example.test;"
                    "1;10;1000;1;01.01.2020;EPSG:25832;350000;5650000"
                ),
            ]
        ),
        encoding="utf-8",
    )
    student_counts_path.write_text(
        "\n".join(
            [
                "Schulnummer;Anzahl",
                "100001;321",
            ]
        ),
        encoding="utf-8",
    )
    socialindex_df = pd.DataFrame(
        [
            {
                "bezirksregierung": "BR Koeln",
                "kreis_kreisfreie_stadt": "Stadt Koeln",
                "schulnummer": 100001,
                "schulname": "Koeln, GG Schule A",
                "sozialindexstufe": 3,
            }
        ]
    )

    result = enrich_with_geodata(
        socialindex_df, str(base_data_path), str(student_counts_path)
    )

    assert result.loc[0, "schulform"] == "Grundschule"
    assert result.loc[0, "schuldaten_schulform"] == "02"
    assert result.loc[0, "anzahl_schueler"] == 321


def test_student_counts_are_read_by_school_number(tmp_path):
    csv_path = tmp_path / "schueler.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Schulnummer;Anzahl",
                "100001;321",
                "100002;",
            ]
        ),
        encoding="utf-8",
    )

    result = _read_student_counts(str(csv_path))

    assert result.to_dict("records") == [
        {"schulnummer": 100001, "anzahl_schueler": 321},
        {"schulnummer": 100002, "anzahl_schueler": None},
    ]
