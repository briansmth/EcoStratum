"""
Chart builders for the EcoIntel dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

COLORS = {
    "primary": "#1a5c2e",
    "secondary": "#4a8c5e",
    "accent": "#2d7a45",
    "danger": "#8b1a1a",
    "warning": "#8b6914",
    "info": "#1a4a6b",
    "neutral": "#555555",
}

IUCN_COLORS = {
    "Critically Endangered": "#8b1a1a",
    "Endangered": "#b35900",
    "Vulnerable": "#b38f00",
    "Near Threatened": "#5a8a3c",
    "Least Concern": "#2d7a45",
    "Data Deficient": "#777777",
    "Not Evaluated": "#999999",
    "Unknown": "#bbbbbb",
}

LAYOUT_DEFAULTS = dict(
    font=dict(family="Source Sans Pro, sans-serif", size=13, color="#2a2a2a"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=44, b=20),
)


def species_by_group_chart(group_df: pd.DataFrame) -> go.Figure:
    if group_df.empty:
        return go.Figure().update_layout(title="No data available")

    df = group_df.sort_values("species_count", ascending=True).tail(15)

    fig = px.bar(
        df,
        x="species_count",
        y="class",
        orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
        labels={"species_count": "Number of species", "class": ""},
    )
    fig.update_layout(
        title="Species by taxonomic group",
        height=max(300, len(df) * 30),
        **LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(gridcolor="#e8e8e8")
    fig.update_yaxes(gridcolor="#e8e8e8")
    return fig


def iucn_breakdown_chart(iucn_df: pd.DataFrame) -> go.Figure:
    if iucn_df.empty:
        return go.Figure().update_layout(title="No IUCN data available")

    colors = [IUCN_COLORS.get(label, "#bbbbbb") for label in iucn_df["label"]]

    fig = go.Figure(
        go.Pie(
            labels=iucn_df["label"],
            values=iucn_df["count"],
            hole=0.45,
            marker=dict(colors=colors),
            textinfo="label+value",
            textposition="outside",
            textfont=dict(size=12),
        )
    )
    fig.update_layout(
        title="IUCN Red List breakdown",
        height=400,
        showlegend=False,
        **LAYOUT_DEFAULTS,
    )
    return fig


def observations_timeline_chart(timeline_df: pd.DataFrame) -> go.Figure:
    if timeline_df.empty:
        return go.Figure().update_layout(title="No temporal data available")

    fig = px.area(
        timeline_df,
        x="year",
        y="observations",
        color_discrete_sequence=[COLORS["secondary"]],
        labels={"year": "Year", "observations": "Observations"},
    )
    fig.update_layout(
        title="Observations over time",
        height=300,
        **LAYOUT_DEFAULTS,
    )
    # Force integer year axis — fixes "2,025.2" issue
    fig.update_xaxes(
        gridcolor="#e8e8e8",
        dtick=1,
        tickformat="d",
    )
    fig.update_yaxes(gridcolor="#e8e8e8")
    return fig


def top_species_chart(top_df: pd.DataFrame) -> go.Figure:
    if top_df.empty:
        return go.Figure().update_layout(title="No data available")

    df = top_df.sort_values("observation_count", ascending=True).tail(20)
    df = df.copy()
    df["label"] = df["species"].apply(
        lambda x: (x[:30] + "...") if len(str(x)) > 30 else x
    )

    fig = px.bar(
        df,
        x="observation_count",
        y="label",
        orientation="h",
        color_discrete_sequence=[COLORS["info"]],
        labels={"observation_count": "Observations", "label": ""},
    )
    fig.update_layout(
        title="Most observed species",
        height=max(400, len(df) * 25),
        **LAYOUT_DEFAULTS,
    )
    fig.update_xaxes(gridcolor="#e8e8e8")
    fig.update_yaxes(gridcolor="#e8e8e8")
    return fig
