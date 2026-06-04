from __future__ import annotations

import pandas as pd
import streamlit as st

from sozialindex_dashboard.db import DB_PATH, read_schulen

st.set_page_config(
    page_title="Sozialindex Schulen NRW",
    page_icon=":material/school:",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
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


df = load_data()

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

filtered_df = filter_data(
    df,
    query,
    selected_bezirksregierungen,
    selected_kreise,
    selected_schulformen,
    selected_sozialindexstufen,
)

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
        },
    )
