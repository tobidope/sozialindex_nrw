from __future__ import annotations

import pandas as pd

from sozialindex_dashboard.extract_pdf import _read_school_base_data


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
