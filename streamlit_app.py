from __future__ import annotations

from urllib.parse import quote_plus

import pandas as pd
import pydeck as pdk
import streamlit as st

from sozialindex_dashboard.config import load_source_config
from sozialindex_dashboard.db import (
    DB_PATH,
    query_schulen,
    read_filter_options,
    read_imported_at,
    read_schulform_counts,
    read_sozialindex_counts,
    read_summary,
)
from sozialindex_dashboard.geolocation import browser_geolocation

NRW_LOGO_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/8/83/Wappenzeichen_NRW.svg"
)
SOCIALINDEX_COLORS: dict[int, str] = {
    1: "#29B09D",
    2: "#7DEFA1",
    3: "#83C9FF",
    4: "#0068C9",
    5: "#FFD16A",
    6: "#FF8700",
    7: "#FFABAB",
    8: "#FF2B2B",
    9: "#6D3FC0",
}
DEFAULT_MAP_COLOR = "#808495"
MAP_COLOR_ALPHA = 220

st.set_page_config(
    page_title="Sozialindex Schulen NRW",
    page_icon=NRW_LOGO_URL,
    layout="wide",
)
st.logo(NRW_LOGO_URL, size="medium", icon_image=NRW_LOGO_URL)


@st.cache_data(show_spinner=False)
def load_filter_options(db_mtime: float) -> dict[str, list]:
    return read_filter_options(DB_PATH)


@st.cache_data(show_spinner=False, max_entries=1)
def load_imported_at(db_mtime: float):
    return read_imported_at(DB_PATH)


@st.cache_data(show_spinner=False, max_entries=1)
def load_schools(
    db_mtime: float,
    query: str,
    bezirksregierungen: tuple[str, ...],
    kreise: tuple[str, ...],
    schulformen: tuple[str, ...],
    sozialindexstufen: tuple[int, ...],
    latitude: float | None,
    longitude: float | None,
    radius_km: int | None,
) -> pd.DataFrame:
    return query_schulen(
        query=query,
        bezirksregierungen=list(bezirksregierungen),
        kreise=list(kreise),
        schulformen=list(schulformen),
        sozialindexstufen=list(sozialindexstufen),
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        db_path=DB_PATH,
    )


@st.cache_data(show_spinner=False, max_entries=1)
def load_summary(
    db_mtime: float,
    query: str,
    bezirksregierungen: tuple[str, ...],
    kreise: tuple[str, ...],
    schulformen: tuple[str, ...],
    sozialindexstufen: tuple[int, ...],
    latitude: float | None,
    longitude: float | None,
    radius_km: int | None,
) -> dict:
    return read_summary(
        query=query,
        bezirksregierungen=list(bezirksregierungen),
        kreise=list(kreise),
        schulformen=list(schulformen),
        sozialindexstufen=list(sozialindexstufen),
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        db_path=DB_PATH,
    )


@st.cache_data(show_spinner=False, max_entries=10)
def load_sozialindex_counts(
    db_mtime: float,
    query: str,
    bezirksregierungen: tuple[str, ...],
    kreise: tuple[str, ...],
    schulformen: tuple[str, ...],
    sozialindexstufen: tuple[int, ...],
    latitude: float | None,
    longitude: float | None,
    radius_km: int | None,
) -> pd.DataFrame:
    return read_sozialindex_counts(
        query=query,
        bezirksregierungen=list(bezirksregierungen),
        kreise=list(kreise),
        schulformen=list(schulformen),
        sozialindexstufen=list(sozialindexstufen),
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        db_path=DB_PATH,
    )


@st.cache_data(show_spinner=False, max_entries=10)
def load_schulform_counts(
    db_mtime: float,
    query: str,
    bezirksregierungen: tuple[str, ...],
    kreise: tuple[str, ...],
    schulformen: tuple[str, ...],
    sozialindexstufen: tuple[int, ...],
    latitude: float | None,
    longitude: float | None,
    radius_km: int | None,
) -> pd.DataFrame:
    return read_schulform_counts(
        query=query,
        bezirksregierungen=list(bezirksregierungen),
        kreise=list(kreise),
        schulformen=list(schulformen),
        sozialindexstufen=list(sozialindexstufen),
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        db_path=DB_PATH,
    )


def render_socialindex_legend() -> None:
    items = []
    for index in range(1, 10):
        items.append(
            f"""
            <div class="legend-item">
                <span class="legend-swatch" style="background: {SOCIALINDEX_COLORS[index]};"></span>
                <span>{index}</span>
            </div>
            """
        )

    st.html(
        f"""
        <style>
        .map-legend {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 8px;
            color: #17211F;
            font-size: 0.875rem;
        }}
        .legend-title {{
            font-weight: 600;
            margin-right: 2px;
        }}
        .legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .legend-swatch {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            border: 1px solid rgba(23, 33, 31, 0.25);
        }}
        </style>
        <div class="map-legend">
            <span class="legend-title">Sozialindexstufe</span>
            {"".join(items)}
        </div>
        """
    )


def hex_to_rgba(hex_color: str, alpha: int = MAP_COLOR_ALPHA) -> list[int]:
    color = hex_color.removeprefix("#")
    return [
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
        alpha,
    ]


def socialindex_color(index: int) -> list[int]:
    return hex_to_rgba(SOCIALINDEX_COLORS.get(int(index), DEFAULT_MAP_COLOR))


def format_address(row: pd.Series) -> str:
    parts = [
        str(row.get("strasse") or "").strip(),
        " ".join(
            part
            for part in [
                str(row.get("plz") or "").strip(),
                str(row.get("ort") or "").strip(),
            ]
            if part
        ),
    ]
    return ", ".join(part for part in parts if part)


def school_display_name(row: pd.Series) -> str:
    short_name = str(row.get("kurzbezeichnung") or "").strip()
    if short_name and short_name != "<NA>":
        return short_name
    return str(row.get("schulname") or "").strip()


def google_maps_search_link(row: pd.Series) -> str:
    query = " ".join(
        part
        for part in [
            school_display_name(row),
            format_address(row),
        ]
        if part
    )
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def school_homepage_link(row: pd.Series) -> str | None:
    homepage = str(row.get("homepage") or "").strip()
    if not homepage or homepage == "<NA>":
        return None
    if homepage.startswith(("http://", "https://")):
        return homepage
    return f"https://{homepage}"


def school_homepage_display_link(row: pd.Series) -> str:
    school_name = school_display_name(row)
    homepage = school_homepage_link(row)
    if homepage is None:
        return f"#schule={school_name}"
    return f"{homepage}#schule={school_name}"


def build_school_list(df: pd.DataFrame, include_distance: bool) -> pd.DataFrame:
    list_df = pd.DataFrame(
        {
            "Schule": df.apply(school_homepage_display_link, axis=1),
            "Schulform": df["schulform"],
            "Sozialindex": df["sozialindexstufe"],
            "Adresse": df.apply(format_address, axis=1),
            "Link": df.apply(google_maps_search_link, axis=1),
        }
    )
    if include_distance and "entfernung_km" in df.columns:
        list_df["Entfernung"] = df["entfernung_km"]
        return list_df.sort_values(
            ["Sozialindex", "Entfernung"], ascending=[True, True]
        )
    return list_df.sort_values("Sozialindex", ascending=True)


source_config = load_source_config()
db_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0
filter_options = load_filter_options(db_mtime)
imported_at = load_imported_at(db_mtime)

st.title("Sozialindex Schulen NRW")
st.caption("Schuljahr 2025/2026")

if not DB_PATH.exists():
    st.warning(
        "Noch keine Datenbank gefunden. Führe zuerst "
        "`uv run python -m sozialindex_dashboard.extract_pdf` aus."
    )
    st.stop()

with st.sidebar:
    st.header("Umkreis")
    radius_km = st.slider(
        "Radius in km",
        min_value=1,
        max_value=50,
        value=5,
        key="radius_km",
        bind="query-params",
    )
    location_result = browser_geolocation(key="browser_geolocation")
    browser_latitude = getattr(location_result, "latitude", None)
    browser_longitude = getattr(location_result, "longitude", None)
    if browser_latitude is not None:
        st.session_state["latitude"] = float(browser_latitude)
    else:
        st.session_state.setdefault("latitude", None)
    if browser_longitude is not None:
        st.session_state["longitude"] = float(browser_longitude)
    else:
        st.session_state.setdefault("longitude", None)

    manual_latitude = st.number_input(
        "Latitude",
        min_value=50.0,
        max_value=53.0,
        value=None,
        format="%.6f",
        key="latitude",
        bind="query-params",
    )
    manual_longitude = st.number_input(
        "Longitude",
        min_value=5.0,
        max_value=10.0,
        value=None,
        format="%.6f",
        key="longitude",
        bind="query-params",
    )

    st.header("Filter")
    query = st.text_input(
        "Suche",
        placeholder="Schulname oder Schulnummer",
        key="suche",
        bind="query-params",
    )
    selected_bezirksregierungen = st.multiselect(
        "Bezirksregierung",
        filter_options["bezirksregierung"],
        placeholder="Bezirksregierung auswählen",
        key="bezirksregierungen",
        bind="query-params",
    )
    selected_kreise = st.multiselect(
        "Kreis / Kreisfreie Stadt",
        filter_options["kreis_kreisfreie_stadt"],
        placeholder="Kreis oder Stadt auswählen",
        key="kreis_stadt",
        bind="query-params",
    )
    selected_schulformen = st.multiselect(
        "Schulform",
        filter_options["schulform"],
        placeholder="Schulform auswählen",
        key="schulformen",
        bind="query-params",
    )
    selected_sozialindexstufen = st.multiselect(
        "Sozialindexstufe",
        filter_options["sozialindexstufe"],
        placeholder="Sozialindexstufe auswählen",
        key="sozialindexstufen",
        bind="query-params",
    )

origin_available = manual_latitude is not None and manual_longitude is not None
origin_latitude = float(manual_latitude) if origin_available else None
origin_longitude = float(manual_longitude) if origin_available else None
active_radius_km = radius_km if origin_available else None
selected_bezirksregierungen_tuple = tuple(selected_bezirksregierungen)
selected_kreise_tuple = tuple(selected_kreise)
selected_schulformen_tuple = tuple(selected_schulformen)
selected_sozialindexstufen_tuple = tuple(int(value) for value in selected_sozialindexstufen)

result_df = load_schools(
    db_mtime,
    query,
    selected_bezirksregierungen_tuple,
    selected_kreise_tuple,
    selected_schulformen_tuple,
    selected_sozialindexstufen_tuple,
    origin_latitude,
    origin_longitude,
    active_radius_km,
)
summary = load_summary(
    db_mtime,
    query,
    selected_bezirksregierungen_tuple,
    selected_kreise_tuple,
    selected_schulformen_tuple,
    selected_sozialindexstufen_tuple,
    origin_latitude,
    origin_longitude,
    active_radius_km,
)
index_counts = load_sozialindex_counts(
    db_mtime,
    query,
    selected_bezirksregierungen_tuple,
    selected_kreise_tuple,
    selected_schulformen_tuple,
    selected_sozialindexstufen_tuple,
    origin_latitude,
    origin_longitude,
    active_radius_km,
)
form_counts = load_schulform_counts(
    db_mtime,
    query,
    selected_bezirksregierungen_tuple,
    selected_kreise_tuple,
    selected_schulformen_tuple,
    selected_sozialindexstufen_tuple,
    origin_latitude,
    origin_longitude,
    active_radius_km,
)

with st.container(horizontal=True):
    st.metric("Schulen", f"{summary['schulen']:,}".replace(",", "."), border=True)
    st.metric(
        "Kreise / kreisfreie Städte",
        f"{summary['kreise']:,}".replace(",", "."),
        border=True,
    )
    st.metric(
        "Schulformen",
        f"{summary['schulformen']:,}".replace(",", "."),
        border=True,
    )
    average_index = summary["durchschnitt_sozialindex"]
    st.metric(
        "Durchschnittliche Stufe",
        f"{average_index:.1f}" if pd.notna(average_index) else "-",
        border=True,
    )
    st.metric(
        "Mit Koordinaten",
        f"{summary['mit_koordinaten']:,}".replace(",", "."),
        border=True,
    )

with st.container(border=True):
    st.subheader("Schulen im Umkreis")
    if not origin_available:
        st.info("Standort ermitteln oder Latitude und Longitude eingeben.")
    elif result_df.empty:
        st.info("Keine Schulen im gewählten Radius gefunden.")
    else:
        map_df = result_df.copy()
        map_df["radius_m"] = 100
        map_df["farbe"] = map_df["sozialindexstufe"].apply(socialindex_color)
        map_df["entfernung_karte"] = map_df["entfernung_km"].map(
            lambda value: f"{value:.1f}"
        )
        view_state = pdk.ViewState(
            latitude=float(manual_latitude),
            longitude=float(manual_longitude),
            zoom=11,
            pitch=0,
        )
        school_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[longitude, latitude]",
            get_fill_color="farbe",
            get_radius="radius_m",
            pickable=True,
            opacity=0.85,
        )
        origin_layer = pdk.Layer(
            "ScatterplotLayer",
            data=pd.DataFrame(
                [
                    {
                        "latitude": float(manual_latitude),
                        "longitude": float(manual_longitude),
                        "radius_m": 180,
                        "farbe": [30, 30, 30, 230],
                    }
                ]
            ),
            get_position="[longitude, latitude]",
            get_fill_color="farbe",
            get_radius="radius_m",
            pickable=False,
        )
        st.pydeck_chart(
            pdk.Deck(
                map_style=None,
                initial_view_state=view_state,
                layers=[school_layer, origin_layer],
                tooltip={
                    "html": (
                        "<b>{kurzbezeichnung}</b><br/>"
                        "Schulnummer: {schulnummer}<br/>"
                        "{schulform}, {ort}<br/>"
                        "Sozialindexstufe: {sozialindexstufe}<br/>"
                        "Entfernung: {entfernung_karte} km"
                    ),
                    "style": {"backgroundColor": "#17211F", "color": "white"},
                },
            )
        )
        render_socialindex_legend()

chart_col, form_col = st.columns(2)

with chart_col:
    with st.container(border=True):
        st.subheader("Verteilung nach Sozialindexstufe")
        st.bar_chart(
            index_counts,
            x="sozialindexstufe",
            y="Anzahl Schulen",
            x_label="Sozialindexstufe",
            y_label="Anzahl Schulen",
        )

with form_col:
    with st.container(border=True):
        st.subheader("Schulen nach Schulform")
        st.bar_chart(
            form_counts,
            x="schulform",
            y="Anzahl Schulen",
            x_label="Schulform",
            y_label="Anzahl Schulen",
        )

with st.container(border=True):
    st.subheader("Schulliste")
    display_df = build_school_list(result_df, include_distance=origin_available)

    st.dataframe(
        display_df,
        hide_index=True,
        column_order=list(display_df.columns),
        column_config={
            "Schule": st.column_config.LinkColumn(
                "Schule",
                display_text=r"#schule=(.*)$",
            ),
            "Sozialindex": st.column_config.NumberColumn(
                "Sozialindex",
                format="%d",
                help="Sozialindexstufe von 1 (niedrig) bis 9 (hoch)",
            ),
            "Link": st.column_config.LinkColumn(
                "Link",
                display_text="Google Maps",
            ),
            "Entfernung": st.column_config.NumberColumn(
                "Entfernung",
                format="%.2f km",
            ),
        },
    )

st.divider()
st.subheader("Datenquellen & Lizenz")
st.markdown(
    f"""
Die dargestellten Daten basieren auf Open Data des Ministeriums für Schule und Bildung
des Landes Nordrhein-Westfalen.

- Sozialindex-Schulliste 2025/26: [PDF]({source_config.socialindex_pdf_url})
- Schulgrunddaten NRW: [CSV]({source_config.school_base_data_url})
- Datenstand: {imported_at.astimezone().strftime("%d.%m.%Y, %H:%M Uhr") if imported_at else "unbekannt"}
- Lizenz: [Datenlizenz Deutschland – Namensnennung – Version 2.0](https://www.govdata.de/dl-de/by-2-0)

Diese Webseite ist kein offizielles Angebot des Ministeriums.
"""
)
