from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from sozialindex_dashboard.db import DB_PATH, read_schulen
from sozialindex_dashboard.geo import add_distance_km, parse_coordinate, socialindex_color
from sozialindex_dashboard.geolocation import browser_geolocation

st.set_page_config(
    page_title="Sozialindex Schulen NRW",
    page_icon=":material/school:",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_data(db_mtime: float) -> pd.DataFrame:
    return read_schulen(DB_PATH)


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
            filtered["schulname"].astype(str)
            + " "
            + filtered["schulnummer"].astype(str)
            + " "
            + filtered["kreis_kreisfreie_stadt"].astype(str)
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


df = load_data(DB_PATH.stat().st_mtime if DB_PATH.exists() else 0)

st.title("Sozialindex Schulen NRW")
st.caption("Schuljahr 2025/2026")

if df.empty:
    st.warning(
        "Noch keine Datenbank gefunden. Führe zuerst "
        "`uv run python -m sozialindex_dashboard.extract_pdf` aus."
    )
    st.stop()

with st.sidebar:
    st.header("Filter")
    query = st.text_input(
        "Suche",
        placeholder="Schulname, Schulnummer oder Kreis",
    )
    selected_bezirksregierungen = st.multiselect(
        "Bezirksregierung",
        sorted(df["bezirksregierung"].dropna().unique()),
    )
    selected_kreise = st.multiselect(
        "Kreis / Kreisfreie Stadt",
        sorted(df["kreis_kreisfreie_stadt"].dropna().unique()),
    )
    selected_schulformen = st.multiselect(
        "Schulform",
        sorted(df["schulform"].dropna().unique()),
    )
    selected_sozialindexstufen = st.multiselect(
        "Sozialindexstufe",
        sorted(df["sozialindexstufe"].dropna().unique()),
    )
    st.header("Umkreis")
    radius_km = st.slider("Radius in km", min_value=1, max_value=50, value=5)
    location_result = browser_geolocation()
    browser_latitude = getattr(location_result, "latitude", None)
    browser_longitude = getattr(location_result, "longitude", None)
    default_latitude = float(browser_latitude) if browser_latitude is not None else None
    default_longitude = float(browser_longitude) if browser_longitude is not None else None
    latitude_text = st.text_input(
        "Latitude",
        value=f"{default_latitude:.6f}" if default_latitude is not None else "",
        placeholder="z.B. 51.4818",
    )
    longitude_text = st.text_input(
        "Longitude",
        value=f"{default_longitude:.6f}" if default_longitude is not None else "",
        placeholder="z.B. 7.2162",
    )
    manual_latitude = parse_coordinate(latitude_text, 50.0, 53.0)
    manual_longitude = parse_coordinate(longitude_text, 5.0, 10.0)
    if latitude_text and manual_latitude is None:
        st.warning("Latitude muss zwischen 50.0 und 53.0 liegen.")
    if longitude_text and manual_longitude is None:
        st.warning("Longitude muss zwischen 5.0 und 10.0 liegen.")

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

with st.container(horizontal=True):
    st.metric("Schulen", f"{len(filtered_df):,}".replace(",", "."), border=True)
    st.metric(
        "Kreise / kreisfreie Städte",
        f"{filtered_df['kreis_kreisfreie_stadt'].nunique():,}".replace(",", "."),
        border=True,
    )
    st.metric(
        "Schulformen",
        f"{filtered_df['schulform'].nunique():,}".replace(",", "."),
        border=True,
    )
    average_index = filtered_df["sozialindexstufe"].mean()
    st.metric(
        "Durchschnittliche Stufe",
        f"{average_index:.1f}" if pd.notna(average_index) else "-",
        border=True,
    )
    st.metric(
        "Mit Koordinaten",
        f"{schools_with_coordinates['schulnummer'].nunique():,}".replace(",", "."),
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
                        "<b>{schulname}</b><br/>"
                        "Schulnummer: {schulnummer}<br/>"
                        "{schulform}, {ort}<br/>"
                        "Sozialindexstufe: {sozialindexstufe}<br/>"
                        "Entfernung: {entfernung_km} km"
                    ),
                    "style": {"backgroundColor": "#17211F", "color": "white"},
                },
            )
        )

chart_col, form_col = st.columns(2)

with chart_col:
    with st.container(border=True):
        st.subheader("Verteilung nach Sozialindexstufe")
        index_counts = (
            filtered_df.groupby("sozialindexstufe", as_index=False)
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
            filtered_df.groupby("schulform", as_index=False)
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
    display_df = filtered_df.rename(
        columns={
            "bezirksregierung": "Bezirksregierung",
            "kreis_kreisfreie_stadt": "Kreis / Kreisfreie Stadt",
            "schulform": "Schulform",
            "schulnummer": "Schulnummer",
            "schulname": "Schulname",
            "sozialindexstufe": "Sozialindexstufe",
            "strasse": "Strasse",
            "plz": "PLZ",
            "ort": "Ort",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "geo_match_status": "Geo-Status",
            "entfernung_km": "Entfernung km",
        }
    )
    if origin_available and not schools_in_radius.empty:
        display_df = schools_in_radius.rename(
            columns={
                "bezirksregierung": "Bezirksregierung",
                "kreis_kreisfreie_stadt": "Kreis / Kreisfreie Stadt",
                "schulform": "Schulform",
                "schulnummer": "Schulnummer",
                "schulname": "Schulname",
                "sozialindexstufe": "Sozialindexstufe",
                "strasse": "Strasse",
                "plz": "PLZ",
                "ort": "Ort",
                "latitude": "Latitude",
                "longitude": "Longitude",
                "geo_match_status": "Geo-Status",
                "entfernung_km": "Entfernung km",
            }
        )
    st.dataframe(
        display_df,
        hide_index=True,
        column_config={
            "Schulnummer": st.column_config.NumberColumn(
                "Schulnummer",
                format="%d",
            ),
            "Sozialindexstufe": st.column_config.NumberColumn(
                "Sozialindexstufe",
                format="%d",
            ),
            "Entfernung km": st.column_config.NumberColumn(
                "Entfernung km",
                format="%.2f",
            ),
            "Latitude": st.column_config.NumberColumn("Latitude", format="%.6f"),
            "Longitude": st.column_config.NumberColumn("Longitude", format="%.6f"),
        },
    )
