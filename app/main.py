"""
EcoStratum — Ecological Site Screener
Run with: streamlit run app/main.py
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import date, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.gbif_client import (
    query_species_in_area,
    get_species_summary,
    get_iucn_threatened,
    get_invasive_species,
    build_detailed_csv,
)
from modules.species_analysis import (
    compute_overview_stats,
    species_by_group,
    observations_by_year,
    iucn_breakdown,
    top_species,
)
from modules.charts import (
    species_by_group_chart,
    iucn_breakdown_chart,
    observations_timeline_chart,
    top_species_chart,
)


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EcoStratum",
    page_icon="E",
    layout="wide",
    initial_sidebar_state="expanded",
)

css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────────────
for key, default in {
    "results_ready": False,
    "raw_df": pd.DataFrame(),
    "query_lat": None,
    "query_lon": None,
    "query_buffer": None,
    "clicked_lat": None,
    "clicked_lon": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.markdown("## SITE SELECTION")

input_method = st.sidebar.radio(
    "Method",
    ["Enter coordinates", "Click on map"],
    index=0,
    label_visibility="collapsed",
)

if input_method == "Enter coordinates":
    st.sidebar.markdown("**Coordinates**")
    col1, col2 = st.sidebar.columns(2)
    lat = col1.number_input(
        "Latitude", value=46.95, min_value=-90.0, max_value=90.0,
        step=0.01, format="%.4f",
    )
    lon = col2.number_input(
        "Longitude", value=7.45, min_value=-180.0, max_value=180.0,
        step=0.01, format="%.4f",
    )
else:
    lat = st.session_state.clicked_lat or 46.95
    lon = st.session_state.clicked_lon or 7.45
    if st.session_state.clicked_lat:
        st.sidebar.info(f"Selected: {lat:.4f}, {lon:.4f}")
    else:
        st.sidebar.info("Click the map below to set coordinates.")

st.sidebar.markdown("**Search radius (km)**")
buffer_km = st.sidebar.number_input(
    "Radius",
    min_value=1,
    max_value=200,
    value=5,
    step=1,
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.markdown("## FILTERS")

st.sidebar.markdown("**Date range**")
use_dates = st.sidebar.checkbox("Filter by date", value=False)
date_from = None
date_to = None
if use_dates:
    col_d1, col_d2 = st.sidebar.columns(2)
    date_from_val = col_d1.date_input(
        "From",
        value=date(2020, 1, 1),
        min_value=date(1900, 1, 1),
        max_value=date.today(),
    )
    date_to_val = col_d2.date_input(
        "To",
        value=date.today(),
        min_value=date(1900, 1, 1),
        max_value=date.today(),
    )
    date_from = date_from_val.isoformat()
    date_to = date_to_val.isoformat()

st.sidebar.markdown("---")
st.sidebar.markdown("## SETTINGS")

st.sidebar.markdown("**Maximum records to fetch**")
max_records = st.sidebar.number_input(
    "Max records",
    min_value=100,
    max_value=5000,
    value=500,
    step=100,
    label_visibility="collapsed",
)

run_query = st.sidebar.button(
    "Run screening", type="primary", use_container_width=True,
)


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("# EcoStratum")
st.markdown("##### Ecological Site Screener")
st.markdown(
    "Enter coordinates or click the map to define a site, set a search radius, "
    "and generate an ecological screening of all recorded species. "
    "Data sourced from [GBIF](https://www.gbif.org)."
)
st.markdown("---")


# ── Map input ────────────────────────────────────────────────────────────────
if input_method == "Click on map":
    m = folium.Map(location=[lat, lon], zoom_start=5, tiles="CartoDB positron")
    if st.session_state.clicked_lat:
        folium.Marker(
            [st.session_state.clicked_lat, st.session_state.clicked_lon],
            icon=folium.Icon(color="darkgreen", icon="circle", prefix="fa"),
        ).add_to(m)
    map_data = st_folium(m, width=None, height=400, key="input_map")

    if map_data and map_data.get("last_clicked"):
        new_lat = map_data["last_clicked"]["lat"]
        new_lon = map_data["last_clicked"]["lng"]
        if (new_lat != st.session_state.clicked_lat
                or new_lon != st.session_state.clicked_lon):
            st.session_state.clicked_lat = new_lat
            st.session_state.clicked_lon = new_lon
            lat = new_lat
            lon = new_lon

    st.markdown("---")


# ── Run query ────────────────────────────────────────────────────────────────
if run_query:
    date_info = ""
    if date_from and date_to:
        date_info = f" | {date_from} to {date_to}"

    with st.spinner(
        f"Querying GBIF within {buffer_km} km of "
        f"({lat:.4f}, {lon:.4f}){date_info}..."
    ):
        raw_df = query_species_in_area(
            lat, lon,
            buffer_km=buffer_km,
            limit=min(max_records, 300),
            date_from=date_from,
            date_to=date_to,
        )

    if raw_df.empty:
        st.warning(
            "No species occurrences found. "
            "Try increasing the search radius, adjusting coordinates, "
            "or expanding the date range."
        )
        st.session_state.results_ready = False
    else:
        st.session_state.raw_df = raw_df
        st.session_state.query_lat = lat
        st.session_state.query_lon = lon
        st.session_state.query_buffer = buffer_km
        st.session_state.results_ready = True


# ── Results ──────────────────────────────────────────────────────────────────
if st.session_state.results_ready:
    raw_df = st.session_state.raw_df
    q_lat = st.session_state.query_lat
    q_lon = st.session_state.query_lon
    q_buffer = st.session_state.query_buffer

    with st.spinner("Analyzing species data and fetching common names..."):
        summary_df = get_species_summary(raw_df)

    stats = compute_overview_stats(raw_df, summary_df)
    threatened_df = get_iucn_threatened(summary_df)
    invasive_df = get_invasive_species(summary_df)
    group_df = species_by_group(summary_df)
    timeline_df = observations_by_year(raw_df)
    iucn_df = iucn_breakdown(summary_df)
    top_df = top_species(summary_df, n=20)
    detailed_export = build_detailed_csv(raw_df)

    st.caption(
        f"Screening results | {q_buffer} km radius | "
        f"({q_lat:.4f}, {q_lon:.4f})"
    )

    # ── Metrics ──────────────────────────────────────────────────────────
    st.markdown("### Overview")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Observations", f"{stats['total_observations']:,}")
    c2.metric("Species", f"{stats['unique_species']:,}")
    c3.metric("Groups", stats["taxonomic_groups"])
    c4.metric("Threatened", stats["threatened_count"])
    c5.metric("Invasive", stats["invasive_count"])
    c6.metric("Period", stats["date_range"])

    # ── Charts ───────────────────────────────────────────────────────────
    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(species_by_group_chart(group_df), use_container_width=True)
    with col_right:
        st.plotly_chart(iucn_breakdown_chart(iucn_df), use_container_width=True)

    col_left2, col_right2 = st.columns(2)
    with col_left2:
        st.plotly_chart(top_species_chart(top_df), use_container_width=True)
    with col_right2:
        st.plotly_chart(observations_timeline_chart(timeline_df), use_container_width=True)

    # ── Occurrence map ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Occurrence map")

    map_df = raw_df.dropna(subset=["decimalLatitude", "decimalLongitude"])
    if not map_df.empty:
        occ_map = folium.Map(
            location=[q_lat, q_lon], zoom_start=11, tiles="CartoDB positron",
        )
        folium.Circle(
            location=[q_lat, q_lon], radius=q_buffer * 1000,
            color="#1a5c2e", fill=True, fill_opacity=0.06, weight=2,
        ).add_to(occ_map)
        folium.Marker(
            [q_lat, q_lon], popup="Search center",
            icon=folium.Icon(color="darkgreen", icon="circle", prefix="fa"),
        ).add_to(occ_map)

        for _, row in map_df.head(500).iterrows():
            folium.CircleMarker(
                location=[row["decimalLatitude"], row["decimalLongitude"]],
                radius=3, color="#1a4a6b", fill=True,
                fill_opacity=0.5, weight=0.5,
                popup=(
                    f"<b>{row.get('species', '')}</b><br>"
                    f"{row.get('observationType', '')}<br>"
                    f"{row.get('eventDate', '')}"
                ),
            ).add_to(occ_map)

        st_folium(occ_map, width=None, height=480, key="result_map")

    # ── Threatened ───────────────────────────────────────────────────────
    if not threatened_df.empty:
        st.markdown("---")
        st.markdown("### Threatened species (IUCN)")
        cols = ["species", "common_name", "class", "family", "iucn_status", "iucn_label", "observation_count"]
        st.dataframe(
            threatened_df[[c for c in cols if c in threatened_df.columns]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

    # ── Invasive ─────────────────────────────────────────────────────────
    if not invasive_df.empty:
        st.markdown("---")
        st.markdown("### Invasive and introduced species")
        cols = ["species", "common_name", "class", "family", "establishment_label", "observation_count"]
        st.dataframe(
            invasive_df[[c for c in cols if c in invasive_df.columns]].reset_index(drop=True),
            use_container_width=True, hide_index=True,
        )

    # ── Full species list ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Complete species list")
    display_cols = [
        "species", "common_name", "class", "order", "family",
        "iucn_label", "establishment_label",
        "observation_count", "first_observed", "last_observed",
    ]
    st.dataframe(
        summary_df[[c for c in display_cols if c in summary_df.columns]].reset_index(drop=True),
        use_container_width=True, hide_index=True, height=400,
    )

    # ── Export ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Export data")

    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Download species summary (CSV)",
            data=summary_df.to_csv(index=False),
            file_name=f"ecostratum_summary_{q_lat:.2f}_{q_lon:.2f}_{q_buffer}km.csv",
            mime="text/csv",
        )
    with dl2:
        if not detailed_export.empty:
            st.download_button(
                "Download detailed observations (CSV)",
                data=detailed_export.to_csv(index=False),
                file_name=f"ecostratum_detailed_{q_lat:.2f}_{q_lon:.2f}_{q_buffer}km.csv",
                mime="text/csv",
            )

    with st.expander("Preview detailed export"):
        if not detailed_export.empty:
            st.dataframe(
                detailed_export.head(10),
                use_container_width=True, hide_index=True,
            )
            st.caption(
                f"{len(detailed_export):,} observations | "
                f"{len(detailed_export.columns)} fields per record"
            )

else:
    st.markdown(
        "Configure your site in the sidebar, then click **Run screening**."
    )


# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Data: GBIF (gbif.org) | EcoStratum v0.5")
