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
from modules.supabase_client import (
    sign_up,
    sign_in,
    sign_out,
    save_search,
    get_search_history,
)


# ── Column label mapping for display tables ─────────────────────────────────
COLUMN_LABELS = {
    "species": "Species",
    "common_name": "Common Name",
    "class": "Class",
    "order": "Order",
    "family": "Family",
    "iucn_status": "IUCN Code",
    "iucn_label": "IUCN Status",
    "observation_count": "Observations",
    "first_observed": "First Observed",
    "last_observed": "Last Observed",
    "establishment_label": "Establishment",
}


def _display_df(df, cols):
    """Prepare a dataframe for display: select columns, fix years, rename."""
    available = [c for c in cols if c in df.columns]
    out = df[available].reset_index(drop=True).copy()
    for col in ["first_observed", "last_observed"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda v: str(int(v)) if pd.notna(v) else ""
            )
    return out.rename(columns=COLUMN_LABELS)


def add_tile_layers(m):
    """Add multiple base map layers and a layer control toggle."""
    folium.TileLayer(
        tiles="https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>',
        name="Light Map",
        show=True,
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Street Map").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Satellite",
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Topographic",
    ).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)


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
    "authenticated": False,
    "user_id": None,
    "user_email": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Auth gate ───────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.markdown(
        '<div class="eco-login-hero">'
        '<h1 class="eco-hero-title">EcoStratum</h1>'
        '<p class="eco-hero-tagline">Ecological Site Screener</p>'
        '<p class="eco-hero-desc">'
        "Screen any location on Earth for recorded species, IUCN threat status, "
        "and invasive species. Powered by GBIF's global biodiversity database "
        "with over 2.4 billion occurrence records."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="eco-login-hero" style="padding-top:20px; padding-bottom:20px;">',
        unsafe_allow_html=True,
    )
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        st.markdown(
            '<div class="eco-feature-card">'
            '<div class="eco-feature-num">500+</div>'
            '<div class="eco-feature-label">Species per site</div>'
            '<div class="eco-feature-desc">Detect all recorded species within a custom search radius</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    with fc2:
        st.markdown(
            '<div class="eco-feature-card">'
            '<div class="eco-feature-num">IUCN</div>'
            '<div class="eco-feature-label">Threat assessment</div>'
            '<div class="eco-feature-desc">Automatic classification from Least Concern to Critically Endangered</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    with fc3:
        st.markdown(
            '<div class="eco-feature-card">'
            '<div class="eco-feature-num">CSV</div>'
            '<div class="eco-feature-label">Export reports</div>'
            '<div class="eco-feature-desc">Download full species summaries and detailed observation records</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")

    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", autocomplete="email")
            password = st.text_input(
                "Password", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button("Log in", use_container_width=True)
            if submitted:
                try:
                    resp = sign_in(email, password)
                    st.session_state.authenticated = True
                    st.session_state.user_id = resp.user.id
                    st.session_state.user_email = resp.user.email
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_signup:
        with st.form("signup_form"):
            new_email = st.text_input("Email", autocomplete="email")
            new_password = st.text_input(
                "Password", type="password", autocomplete="new-password"
            )
            confirm_password = st.text_input(
                "Confirm password", type="password", autocomplete="new-password"
            )
            submitted = st.form_submit_button(
                "Create account", use_container_width=True
            )
            if submitted:
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        sign_up(new_email, new_password)
                        resp = sign_in(new_email, new_password)
                        st.session_state.authenticated = True
                        st.session_state.user_id = resp.user.id
                        st.session_state.user_email = resp.user.email
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.stop()


# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.markdown(f"Logged in as **{st.session_state.user_email}**")
if st.sidebar.button("Log out"):
    sign_out()
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.rerun()

with st.sidebar.expander("Recent searches", expanded=False):
    history = get_search_history(st.session_state.user_id)
    if history:
        for h in history:
            st.markdown(
                f"**{h['lat']:.4f}, {h['lon']:.4f}** "
                f"&middot; {h['radius_km']} km "
                f"&middot; <span style='color:#888;font-size:0.8rem'>{h['searched_at'][:10]}</span>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No searches yet.")

st.sidebar.markdown("---")
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
st.markdown(
    '<p class="eco-app-title">EcoStratum</p>'
    '<p class="eco-app-subtitle">'
    "Ecological Site Screener &mdash; select a location, define a search radius, "
    "and generate a biodiversity screening report. "
    'Data sourced from <a href="https://www.gbif.org" target="_blank">GBIF</a>.'
    "</p>",
    unsafe_allow_html=True,
)
st.markdown("---")


# ── Map input ────────────────────────────────────────────────────────────────
if input_method == "Click on map":
    m = folium.Map(location=[lat, lon], zoom_start=5, tiles=None)
    if st.session_state.clicked_lat:
        folium.Marker(
            [st.session_state.clicked_lat, st.session_state.clicked_lon],
            icon=folium.Icon(color="darkgreen", icon="circle", prefix="fa"),
        ).add_to(m)
    add_tile_layers(m)
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
        try:
            save_search(st.session_state.user_id, lat, lon, buffer_km)
        except Exception:
            pass


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
    st.markdown("### Occurrence Map")

    map_df = raw_df.dropna(subset=["decimalLatitude", "decimalLongitude"])
    if not map_df.empty:
        occ_map = folium.Map(
            location=[q_lat, q_lon], zoom_start=11, tiles=None,
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

        add_tile_layers(occ_map)
        st_folium(occ_map, width=None, height=480, key="result_map")

    # ── Threatened ───────────────────────────────────────────────────────
    if not threatened_df.empty:
        st.markdown("---")
        st.markdown("### Threatened Species (IUCN)")
        cols = ["species", "common_name", "class", "family", "iucn_status", "iucn_label", "observation_count"]
        st.dataframe(
            _display_df(threatened_df, cols),
            use_container_width=True, hide_index=True,
        )

    # ── Invasive ─────────────────────────────────────────────────────────
    if not invasive_df.empty:
        st.markdown("---")
        st.markdown("### Invasive and Introduced Species")
        cols = ["species", "common_name", "class", "family", "establishment_label", "observation_count"]
        st.dataframe(
            _display_df(invasive_df, cols),
            use_container_width=True, hide_index=True,
        )

    # ── Full species list ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Complete Species List")
    display_cols = [
        "species", "common_name", "class", "order", "family",
        "iucn_label", "establishment_label",
        "observation_count", "first_observed", "last_observed",
    ]
    st.dataframe(
        _display_df(summary_df, display_cols),
        use_container_width=True, hide_index=True, height=400,
    )

    # ── Export ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Export Data")

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

    # ── Methodology ──────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("Methodology & Data Sources"):
        st.markdown(
            """
**Data source.** All occurrence records are retrieved from the
[Global Biodiversity Information Facility (GBIF)](https://www.gbif.org),
an international network aggregating biodiversity data from institutions
worldwide.

**Search method.** EcoStratum queries the GBIF Occurrence API using a
bounding-box approximation of the specified search radius around the
target coordinates. Only georeferenced records without known geospatial
issues are included.

**IUCN Red List status.** Threat categories (CR, EN, VU, NT, LC) are
derived from the `iucnRedListCategory` field in GBIF occurrence records.
These may not reflect the most current IUCN assessment. For authoritative
status, consult the [IUCN Red List](https://www.iucnredlist.org).

**Limitations.** GBIF data reflects contributed observations and specimens.
Absence of records does not confirm absence of a species. Observation
density varies by region and taxonomic group.

**Citation.** GBIF.org ({date.today().year}), GBIF Occurrence Download,
accessed via EcoStratum.
            """.strip()
        )

else:
    st.markdown(
        "Configure your site in the sidebar, then click **Run screening**."
    )


# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div class="eco-footer">'
    "Data: "
    '<a href="https://www.gbif.org" target="_blank">Global Biodiversity Information Facility (GBIF)</a>'
    '<div class="eco-footer-links">'
    '<a href="https://www.gbif.org" target="_blank">GBIF</a>'
    '<a href="https://github.com/briansmth/EcoStratum" target="_blank">GitHub</a>'
    '<a href="https://www.linkedin.com/in/briansmth" target="_blank">LinkedIn</a>'
    "</div>"
    '<div class="eco-footer-note">'
    "EcoStratum v1.1 &middot; Occurrence data may not reflect current species distributions. "
    "For authoritative conservation assessments, consult the IUCN Red List."
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)
