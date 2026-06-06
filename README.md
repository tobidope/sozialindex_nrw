# Dashboard Sozialindex der Schulen NRW

Streamlit-Dashboard fuer die Sozialindexstufen der Schulen in NRW im Schuljahr 2025/2026.

## Installation

```bash
uv sync
```

## Daten importieren

Die Datenquellen sind in `config.toml` konfigurierbar:

```toml
[sources]
socialindex_csv_url = "https://www.schulministerium.nrw/system/files/media/document/file/schulliste_sj_25_26_open_data.csv"
school_base_data_url = "https://www.schulministerium.nrw.de/BiPo/OpenData/Schuldaten/schuldaten.csv"
```

Import nach DuckDB:

```bash
uv run python -m sozialindex_dashboard.extract_csv
```

Der Import laedt die Sozialindex-CSV aus der konfigurierten URL, extrahiert die
Sozialindexdaten und reichert sie mit den offiziellen NRW-Schulgrunddaten an.

Die Datenbank wird unter `data/sozialindex.duckdb` erstellt. Die Schulgrunddaten
liefern Adresse und UTM-Koordinaten, die beim Import nach WGS84 transformiert
werden.

## Dashboard starten

```bash
uv run streamlit run streamlit_app.py
```

Das Dashboard bietet Suche nach Schulname, Schulnummer und Kreis sowie Filter fuer
Bezirksregierung, Kreis / kreisfreie Stadt, Schulform und Sozialindexstufe.

Die Umkreissuche nutzt Browser-Standortfreigabe oder manuell eingegebene
Latitude/Longitude-Koordinaten. Es werden keine Adressen an externe
Geocoding-Dienste gesendet.
