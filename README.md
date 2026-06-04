# Dashboard Sozialindex der Schulen NRW

Streamlit-Dashboard fuer die Sozialindexstufen der Schulen in NRW im Schuljahr 2025/2026.

## Installation

```bash
uv sync
```

## Daten aus der PDF importieren

Die PDF liegt im Projektverzeichnis:

```text
sozialindex_schulliste_schuljahr_2025-26.pdf
```

Import nach DuckDB:

```bash
uv run python -m sozialindex_dashboard.extract_pdf
```

Die Datenbank wird unter `data/sozialindex.duckdb` erstellt.

## Dashboard starten

```bash
uv run streamlit run streamlit_app.py
```

Das Dashboard bietet Suche nach Schulname, Schulnummer und Kreis sowie Filter fuer Bezirksregierung, Kreis / kreisfreie Stadt, Schulform und Sozialindexstufe.
