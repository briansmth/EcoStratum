"""
Species analysis: compute ecological statistics from GBIF data.
"""

import pandas as pd
from typing import Dict, Any


def compute_overview_stats(
    raw_df: pd.DataFrame, summary_df: pd.DataFrame
) -> Dict[str, Any]:
    if raw_df.empty:
        return {
            "total_observations": 0,
            "unique_species": 0,
            "taxonomic_groups": 0,
            "threatened_count": 0,
            "invasive_count": 0,
            "date_range": "N/A",
        }

    threatened_cats = ["CR", "EN", "VU", "NT"]
    invasive_terms = ["INTRODUCED", "INVASIVE", "NATURALISED", "MANAGED"]

    threatened = summary_df[
        summary_df.get("iucn_status", pd.Series()).isin(threatened_cats)
    ] if "iucn_status" in summary_df.columns else pd.DataFrame()

    invasive = summary_df[
        summary_df.get("establishment", pd.Series()).fillna("").str.upper().isin(invasive_terms)
    ] if "establishment" in summary_df.columns else pd.DataFrame()

    year_min = raw_df["year"].dropna().min() if "year" in raw_df.columns else None
    year_max = raw_df["year"].dropna().max() if "year" in raw_df.columns else None

    if year_min and year_max:
        date_range = f"{int(year_min)}-{int(year_max)}"
    elif year_min:
        date_range = str(int(year_min))
    else:
        date_range = "N/A"

    return {
        "total_observations": len(raw_df),
        "unique_species": len(summary_df),
        "taxonomic_groups": summary_df["class"].nunique() if "class" in summary_df.columns else 0,
        "threatened_count": len(threatened),
        "invasive_count": len(invasive),
        "date_range": date_range,
    }


def species_by_group(summary_df: pd.DataFrame, group_col: str = "class") -> pd.DataFrame:
    if summary_df.empty or group_col not in summary_df.columns:
        return pd.DataFrame()
    return (
        summary_df.groupby(group_col)
        .agg(species_count=("species", "nunique"))
        .reset_index()
        .sort_values("species_count", ascending=False)
    )


def observations_by_year(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty or "year" not in raw_df.columns:
        return pd.DataFrame()
    result = (
        raw_df.dropna(subset=["year"])
        .groupby("year")
        .size()
        .reset_index(name="observations")
        .sort_values("year")
    )
    # Ensure year is integer
    result["year"] = result["year"].astype(int)
    return result


def iucn_breakdown(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty or "iucn_status" not in summary_df.columns:
        return pd.DataFrame()

    label_map = {
        "LC": "Least Concern",
        "NT": "Near Threatened",
        "VU": "Vulnerable",
        "EN": "Endangered",
        "CR": "Critically Endangered",
        "DD": "Data Deficient",
        "NE": "Not Evaluated",
    }

    # Filter out empty/blank statuses — don't show "Unknown"
    filtered = summary_df["iucn_status"].replace("", pd.NA).dropna()
    if filtered.empty:
        return pd.DataFrame()

    counts = filtered.value_counts().reset_index()
    counts.columns = ["category", "count"]
    counts["label"] = counts["category"].map(lambda x: label_map.get(x, x))
    return counts


def top_species(summary_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()
    return summary_df.nlargest(n, "observation_count")
