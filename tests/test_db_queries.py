from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from sozialindex_dashboard.db import (
    COLUMNS,
    query_schulen,
    read_filter_options,
    read_imported_at,
    read_school_by_number,
    read_schulform_counts,
    read_sozialindex_counts,
    read_summary,
    write_schulen,
)


def _row(**overrides):
    row = {
        "bezirksregierung": "BR Test",
        "kreis_kreisfreie_stadt": "Stadt A",
        "schulform": "Grundschule",
        "schulnummer": 100001,
        "schulname": "Stadt A, GG Alte Schule",
        "sozialindexstufe": 2,
        "anzahl_schueler": 240,
        "strasse": "Schulstr. 1",
        "plz": "50000",
        "ort": "Stadt A",
        "latitude": 51.0,
        "longitude": 7.0,
        "geo_match_status": "matched",
        "schuldaten_schulform": "2",
        "schulbezeichnung_1": "Alte Schule",
        "schulbezeichnung_2": "",
        "schulbezeichnung_3": "",
        "kurzbezeichnung": "Stadt A, GG Alte Schule",
        "schuldaten_bezirksregierung": "1",
        "telefonvorwahl": "0211",
        "telefon": "123",
        "faxvorwahl": "0211",
        "fax": "456",
        "email": "schule@example.test",
        "homepage": "https://schule.example.test",
        "rechtsform": "1",
        "traegernummer": "10",
        "gemeindeschluessel": "1000",
        "schulbetriebsschluessel": "1",
        "schulbetriebsdatum": "01.01.2020",
        "epsg": "EPSG:25832",
        "utm_rechtswert": 350000.0,
        "utm_hochwert": 5650000.0,
    }
    row.update(overrides)
    return row


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.duckdb"
    df = pd.DataFrame(
        [
            _row(),
            _row(
                kreis_kreisfreie_stadt="Stadt A",
                schulform="Gymnasium",
                schulnummer=100002,
                schulname="Stadt A, Gym Weiter Weg",
                sozialindexstufe=5,
                kurzbezeichnung="Stadt A, Gym Weiter Weg",
                latitude=51.2,
                longitude=7.2,
            ),
            _row(
                bezirksregierung="BR Andere",
                kreis_kreisfreie_stadt="Kreis B",
                schulnummer=100003,
                schulname="Kreis B, GG Waldschule",
                sozialindexstufe=8,
                kurzbezeichnung="Kreis B, GG Neuer Name",
                latitude=51.01,
                longitude=7.01,
            ),
        ],
        columns=COLUMNS,
    )
    imported_at = datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc)
    write_schulen(df, path, imported_at=imported_at)
    return path


def test_read_filter_options_are_sorted_and_distinct(db_path):
    options = read_filter_options(db_path)

    assert options["bezirksregierung"] == ["BR Andere", "BR Test"]
    assert options["kreis_kreisfreie_stadt"] == ["Kreis B", "Stadt A"]
    assert options["schulform"] == ["Grundschule", "Gymnasium"]
    assert options["sozialindexstufe"] == [2, 5, 8]


def test_query_searches_short_name_original_name_and_school_number(db_path):
    by_short_name = query_schulen(
        query="Neuer Name",
        bezirksregierungen=[],
        kreise=[],
        schulformen=[],
        sozialindexstufen=[],
        db_path=db_path,
    )
    by_original_name = query_schulen(
        query="Waldschule",
        bezirksregierungen=[],
        kreise=[],
        schulformen=[],
        sozialindexstufen=[],
        db_path=db_path,
    )
    by_number = query_schulen(
        query="100002",
        bezirksregierungen=[],
        kreise=[],
        schulformen=[],
        sozialindexstufen=[],
        db_path=db_path,
    )

    assert by_short_name["schulnummer"].tolist() == [100003]
    assert by_original_name["schulnummer"].tolist() == [100003]
    assert by_number["schulnummer"].tolist() == [100002]


def test_query_combines_list_filters(db_path):
    result = query_schulen(
        query="",
        bezirksregierungen=["BR Test"],
        kreise=["Stadt A"],
        schulformen=["Grundschule"],
        sozialindexstufen=[2],
        db_path=db_path,
    )

    assert result["schulnummer"].tolist() == [100001]


def test_read_school_by_number_returns_matching_school(db_path):
    result = read_school_by_number(100002, db_path=db_path)

    assert result is not None
    assert result["schulnummer"] == 100002
    assert result["schulname"] == "Stadt A, Gym Weiter Weg"
    assert "entfernung_km" not in result.index


def test_read_school_by_number_can_include_distance(db_path):
    result = read_school_by_number(
        100001,
        latitude=51.0,
        longitude=7.0,
        db_path=db_path,
    )

    assert result is not None
    assert result["schulnummer"] == 100001
    assert result["entfernung_km"] == pytest.approx(0)


def test_read_school_by_number_returns_none_for_unknown_school(db_path):
    assert read_school_by_number(999999, db_path=db_path) is None


def test_radius_filter_returns_only_nearby_schools_with_distance(db_path):
    result = query_schulen(
        query="",
        bezirksregierungen=[],
        kreise=[],
        schulformen=[],
        sozialindexstufen=[],
        latitude=51.0,
        longitude=7.0,
        radius_km=2,
        db_path=db_path,
    )

    assert result["schulnummer"].tolist() == [100001, 100003]
    assert "entfernung_km" in result.columns
    assert result.loc[result["schulnummer"] == 100001, "entfernung_km"].iloc[
        0
    ] == pytest.approx(0)
    assert result["entfernung_km"].is_monotonic_increasing


def test_summary_and_chart_counts_use_same_filtered_dataset(db_path):
    kwargs = {
        "query": "",
        "bezirksregierungen": [],
        "kreise": [],
        "schulformen": [],
        "sozialindexstufen": [],
        "latitude": 51.0,
        "longitude": 7.0,
        "radius_km": 2,
        "db_path": db_path,
    }

    summary = read_summary(**kwargs)
    index_counts = read_sozialindex_counts(**kwargs)
    form_counts = read_schulform_counts(**kwargs)

    assert summary == {
        "schulen": 2,
        "kreise": 2,
        "schulformen": 1,
        "durchschnitt_sozialindex": 5.0,
        "mit_koordinaten": 2,
    }
    assert dict(
        zip(
            index_counts["sozialindexstufe"],
            index_counts["Anzahl Schulen"],
            strict=True,
        )
    ) == {
        2: 1,
        8: 1,
    }
    assert form_counts.to_dict("records") == [
        {"schulform": "Grundschule", "Anzahl Schulen": 2}
    ]


def test_import_metadata_roundtrip(db_path):
    assert read_imported_at(db_path) == datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc)
