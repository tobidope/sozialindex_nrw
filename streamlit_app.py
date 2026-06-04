from __future__ import annotations

from urllib.parse import quote_plus

import pandas as pd
import pydeck as pdk
import streamlit as st

from sozialindex_dashboard.config import load_source_config
from sozialindex_dashboard.db import DB_PATH, read_imported_at, read_schulen
from sozialindex_dashboard.geo import (
    add_distance_km,
    parse_coordinate,
    socialindex_color,
)
from sozialindex_dashboard.geolocation import browser_geolocation

NRW_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/8/83/Wappenzeichen_NRW.svg"

st.set_page_config(
    page_title="Sozialindex Schulen NRW",
    page_icon=NRW_LOGO_URL,
    layout="wide",
)
st.logo(NRW_LOGO_URL, size="medium", icon_image=NRW_LOGO_URL)


@st.cache_data(show_spinner=False)
def load_data(db_mtime: float) -> pd.DataFrame:
    return read_schulen(DB_PATH)


@st.cache_data(show_spinner=False)
def load_imported_at(db_mtime: float):
    return read_imported_at(DB_PATH)


def filter_data(
    df: pd.DataFrame,
    query: str,
    bezirksregierungen: list[str],
    kreise: list[str],
    schulformen: list[str],
    sozialindexstufen: list[int],
) -> pd.DataFrame:
    filtered = df.copy()

    if query:
        search_space = (
            filtered["kurzbezeichnung"].astype(str)
            + " "
            + filtered["schulname"].astype(str)
            + " "
            + filtered["schulnummer"].astype(str)
        ).str.lower()
        filtered = filtered[search_space.str.contains(query.lower(), regex=False)]

    if bezirksregierungen:
        filtered = filtered[filtered["bezirksregierung"].isin(bezirksregierungen)]
    if kreise:
        filtered = filtered[filtered["kreis_kreisfreie_stadt"].isin(kreise)]
    if schulformen:
        filtered = filtered[filtered["schulform"].isin(schulformen)]
    if sozialindexstufen:
        filtered = filtered[filtered["sozialindexstufe"].isin(sozialindexstufen)]

    return filtered


def render_socialindex_legend() -> None:
    items = []
    for index in range(1, 10):
        red, green, blue, _alpha = socialindex_color(index)
        items.append(
            f"""
            <div class="legend-item">
                <span class="legend-swatch" style="background: rgb({red}, {green}, {blue});"></span>
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
df = load_data(db_mtime)
imported_at = load_imported_at(db_mtime)

st.title("Sozialindex Schulen NRW")
st.caption("Schuljahr 2025/2026")

if df.empty:
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
        st.session_state["latitude"] = f"{float(browser_latitude):.6f}"
    else:
        st.session_state.setdefault("latitude", "")
    if browser_longitude is not None:
        st.session_state["longitude"] = f"{float(browser_longitude):.6f}"
    else:
        st.session_state.setdefault("longitude", "")

    latitude_text = st.text_input(
        "Latitude",
        placeholder="z.B. 51.4818",
        key="latitude",
        bind="query-params",
    )
    longitude_text = st.text_input(
        "Longitude",
        placeholder="z.B. 7.2162",
        key="longitude",
        bind="query-params",
    )
    manual_latitude = parse_coordinate(latitude_text, 50.0, 53.0)
    manual_longitude = parse_coordinate(longitude_text, 5.0, 10.0)
    if latitude_text and manual_latitude is None:
        st.warning("Latitude muss zwischen 50.0 und 53.0 liegen.")
    if longitude_text and manual_longitude is None:
        st.warning("Longitude muss zwischen 5.0 und 10.0 liegen.")

    st.header("Filter")
    query = st.text_input(
        "Suche",
        placeholder="Schulname oder Schulnummer",
        key="suche",
        bind="query-params",
    )
    selected_bezirksregierungen = st.multiselect(
        "Bezirksregierung",
        sorted(df["bezirksregierung"].dropna().unique()),
        placeholder="Bezirksregierung auswählen",
        key="bezirksregierungen",
        bind="query-params",
    )
    selected_kreise = st.multiselect(
        "Kreis / Kreisfreie Stadt",
        sorted(df["kreis_kreisfreie_stadt"].dropna().unique()),
        placeholder="Kreis oder Stadt auswählen",
        key="kreis_stadt",
        bind="query-params",
    )
    selected_schulformen = st.multiselect(
        "Schulform",
        sorted(df["schulform"].dropna().unique()),
        placeholder="Schulform auswählen",
        key="schulformen",
        bind="query-params",
    )
    selected_sozialindexstufen = st.multiselect(
        "Sozialindexstufe",
        sorted(df["sozialindexstufe"].dropna().unique()),
        placeholder="Sozialindexstufe auswählen",
        key="sozialindexstufen",
        bind="query-params",
    )

filtered_df = filter_data(
    df,
    query,
    selected_bezirksregierungen,
    selected_kreise,
    selected_schulformen,
    selected_sozialindexstufen,
)

origin_available = manual_latitude is not None and manual_longitude is not None
schools_with_coordinates = filtered_df.dropna(subset=["latitude", "longitude"]).copy()
schools_in_radius = pd.DataFrame(columns=[*filtered_df.columns, "entfernung_km"])
if origin_available and not schools_with_coordinates.empty:
    schools_with_distance = add_distance_km(
        schools_with_coordinates,
        float(manual_latitude),
        float(manual_longitude),
    )
    schools_in_radius = schools_with_distance[
        schools_with_distance["entfernung_km"] <= radius_km
    ].sort_values("entfernung_km")

result_df = schools_in_radius if origin_available else filtered_df
result_with_coordinates = result_df.dropna(subset=["latitude", "longitude"]).copy()

with st.container(horizontal=True):
    st.metric("Schulen", f"{len(result_df):,}".replace(",", "."), border=True)
    st.metric(
        "Kreise / kreisfreie Städte",
        f"{result_df['kreis_kreisfreie_stadt'].nunique():,}".replace(",", "."),
        border=True,
    )
    st.metric(
        "Schulformen",
        f"{result_df['schulform'].nunique():,}".replace(",", "."),
        border=True,
    )
    average_index = result_df["sozialindexstufe"].mean()
    st.metric(
        "Durchschnittliche Stufe",
        f"{average_index:.1f}" if pd.notna(average_index) else "-",
        border=True,
    )
    st.metric(
        "Mit Koordinaten",
        f"{result_with_coordinates['schulnummer'].nunique():,}".replace(",", "."),
        border=True,
    )

with st.container(border=True):
    st.subheader("Schulen im Umkreis")
    if not origin_available:
        st.info("Standort ermitteln oder Latitude und Longitude eingeben.")
    elif schools_in_radius.empty:
        st.info("Keine Schulen im gewählten Radius gefunden.")
    else:
        map_df = schools_in_radius.copy()
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
        index_counts = (
            result_df.groupby("sozialindexstufe", as_index=False)
            .size()
            .rename(columns={"size": "Anzahl Schulen"})
            .sort_values("sozialindexstufe")
        )
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
        form_counts = (
            result_df.groupby("schulform", as_index=False)
            .size()
            .rename(columns={"size": "Anzahl Schulen"})
            .sort_values("Anzahl Schulen", ascending=False)
        )
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
