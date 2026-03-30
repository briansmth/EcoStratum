"""
GBIF Occurrence API client.
"""

import requests
import pandas as pd
from typing import Optional
import math

GBIF_API = "https://api.gbif.org/v1"

BASIS_OF_RECORD_MAP = {
    "HUMAN_OBSERVATION": "Direct observation (visual)",
    "MACHINE_OBSERVATION": "Machine observation (camera trap / acoustic)",
    "PRESERVED_SPECIMEN": "Preserved specimen (museum / collection)",
    "FOSSIL_SPECIMEN": "Fossil specimen",
    "MATERIAL_SAMPLE": "Material sample (feces / tissue / DNA)",
    "LIVING_SPECIMEN": "Living specimen (zoo / botanical garden)",
    "OBSERVATION": "Observation (unspecified)",
    "MATERIAL_CITATION": "Material citation (literature)",
    "OCCURRENCE": "Occurrence (unspecified)",
}

IUCN_LABEL_MAP = {
    "LC": "Least Concern",
    "NT": "Near Threatened",
    "VU": "Vulnerable",
    "EN": "Endangered",
    "CR": "Critically Endangered",
    "DD": "Data Deficient",
    "NE": "Not Evaluated",
    "EW": "Extinct in the Wild",
    "EX": "Extinct",
}

ESTABLISHMENT_MAP = {
    "NATIVE": "Native",
    "INTRODUCED": "Introduced",
    "INVASIVE": "Invasive",
    "MANAGED": "Managed",
    "NATURALISED": "Naturalised",
    "UNCERTAIN": "Uncertain",
}


def point_to_bbox(lat: float, lon: float, buffer_km: float) -> dict:
    d_lat = buffer_km / 111.0
    d_lon = buffer_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return {
        "decimalLatitude": f"{lat - d_lat:.4f},{lat + d_lat:.4f}",
        "decimalLongitude": f"{lon - d_lon:.4f},{lon + d_lon:.4f}",
    }


def fetch_common_names(species_list: list) -> dict:
    """
    Look up common names from GBIF Species API.
    Returns dict: scientific name -> common name.
    """
    names = {}
    for sp in species_list[:150]:
        try:
            resp = requests.get(
                f"{GBIF_API}/species/match",
                params={"name": sp, "verbose": "false"},
                timeout=5,
            )
            if resp.ok:
                data = resp.json()
                # Try vernacularName from match
                vn = data.get("vernacularName", "")
                if vn:
                    names[sp] = vn
                    continue
                # Try species detail endpoint for vernacular names
                usage_key = data.get("usageKey")
                if usage_key:
                    vn_resp = requests.get(
                        f"{GBIF_API}/species/{usage_key}/vernacularNames",
                        params={"limit": 5},
                        timeout=5,
                    )
                    if vn_resp.ok:
                        vn_data = vn_resp.json().get("results", [])
                        # Prefer English, then French, then first available
                        for lang in ["eng", "en", "fra", "fr"]:
                            for item in vn_data:
                                if item.get("language", "").lower().startswith(lang[:2]):
                                    names[sp] = item["vernacularName"]
                                    break
                            if sp in names:
                                break
                        if sp not in names and vn_data:
                            names[sp] = vn_data[0].get("vernacularName", "")
        except requests.RequestException:
            continue
    return names


def query_species_in_area(
    lat: float,
    lon: float,
    buffer_km: float = 10.0,
    limit: int = 300,
    country_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    bbox = point_to_bbox(lat, lon, buffer_km)

    params = {
        "decimalLatitude": bbox["decimalLatitude"],
        "decimalLongitude": bbox["decimalLongitude"],
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "limit": limit,
        "offset": 0,
    }

    if country_code:
        params["country"] = country_code

    # Date filter: GBIF uses eventDate with range syntax "2020-01-01,2024-12-31"
    if date_from and date_to:
        params["eventDate"] = f"{date_from},{date_to}"
    elif date_from:
        params["eventDate"] = f"{date_from},*"
    elif date_to:
        params["eventDate"] = f"*,{date_to}"

    all_results = []
    total_fetched = 0
    max_records = 2000

    while total_fetched < max_records:
        params["offset"] = total_fetched
        try:
            resp = requests.get(
                f"{GBIF_API}/occurrence/search",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"GBIF API error: {e}")
            break

        results = data.get("results", [])
        if not results:
            break

        all_results.extend(results)
        total_fetched += len(results)

        if data.get("endOfRecords", True):
            break

    if not all_results:
        return pd.DataFrame()

    rows = []
    for r in all_results:
        iucn_code = r.get("iucnRedListCategory") or ""
        estab_raw = r.get("establishmentMeans") or ""
        ind_count = r.get("individualCount")

        row = {
            "scientificName": r.get("species") or r.get("scientificName") or "",
            "vernacularName": r.get("vernacularName") or "",
            "kingdom": r.get("kingdom") or "",
            "phylum": r.get("phylum") or "",
            "class": r.get("class") or "",
            "order": r.get("order") or "",
            "family": r.get("family") or "",
            "genus": r.get("genus") or "",
            "species": r.get("species") or "",
            "iucnRedListCategory": iucn_code if iucn_code else "",
            "iucnLabel": IUCN_LABEL_MAP.get(iucn_code, ""),
            "establishmentMeans": estab_raw if estab_raw else "",
            "establishmentLabel": ESTABLISHMENT_MAP.get(
                str(estab_raw).upper(), ""
            ),
            "decimalLatitude": r.get("decimalLatitude"),
            "decimalLongitude": r.get("decimalLongitude"),
            "eventDate": r.get("eventDate") or "",
            "year": r.get("year"),
            "month": r.get("month"),
            "day": r.get("day"),
            "basisOfRecord": r.get("basisOfRecord") or "",
            "observationType": BASIS_OF_RECORD_MAP.get(
                r.get("basisOfRecord", ""), "Unknown"
            ),
            # Fix: ensure individualCount is always string to avoid Arrow error
            "individualCount": str(int(ind_count)) if ind_count is not None else "",
            "recordedBy": r.get("recordedBy") or "",
            "datasetName": r.get("datasetName") or "",
            "institutionCode": r.get("institutionCode") or "",
            "countryCode": r.get("countryCode") or "",
            "stateProvince": r.get("stateProvince") or "",
            "locality": r.get("locality") or "",
            "occurrenceID": r.get("occurrenceID") or "",
            "gbifID": str(r.get("gbifID", "")),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if "species" in df.columns:
        df = df[df["species"].astype(str).str.strip() != ""]

    return df


def get_species_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby(["species", "kingdom", "phylum", "class", "order", "family"])
        .agg(
            observation_count=("species", "size"),
            iucn_status=("iucnRedListCategory", "first"),
            iucn_label=("iucnLabel", "first"),
            establishment=("establishmentMeans", "first"),
            establishment_label=("establishmentLabel", "first"),
            common_name=("vernacularName", "first"),
            first_observed=("year", "min"),
            last_observed=("year", "max"),
        )
        .reset_index()
        .sort_values("observation_count", ascending=False)
    )

    # Fetch missing common names from GBIF Species API
    missing = summary[
        summary["common_name"].fillna("").str.strip() == ""
    ]["species"].tolist()

    if missing:
        lookup = fetch_common_names(missing)
        summary["common_name"] = summary.apply(
            lambda row: row["common_name"]
            if str(row["common_name"]).strip()
            else lookup.get(row["species"], ""),
            axis=1,
        )

    # Force year columns to int (avoids "2,025" comma formatting)
    for col in ["first_observed", "last_observed"]:
        if col in summary.columns:
            summary[col] = pd.to_numeric(summary[col], errors="coerce")
            mask = summary[col].notna()
            summary.loc[mask, col] = summary.loc[mask, col].astype(int)

    return summary


def get_iucn_threatened(summary_df: pd.DataFrame) -> pd.DataFrame:
    threatened = ["CR", "EN", "VU", "NT"]
    if "iucn_status" not in summary_df.columns:
        return pd.DataFrame()
    return summary_df[summary_df["iucn_status"].isin(threatened)].copy()


def get_invasive_species(summary_df: pd.DataFrame) -> pd.DataFrame:
    invasive_terms = ["INTRODUCED", "INVASIVE", "NATURALISED", "MANAGED"]
    if "establishment" not in summary_df.columns:
        return pd.DataFrame()
    return summary_df[
        summary_df["establishment"].fillna("").str.upper().isin(invasive_terms)
    ].copy()


def build_detailed_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    export_cols = {
        "scientificName": "Scientific Name",
        "vernacularName": "Common Name",
        "kingdom": "Kingdom",
        "phylum": "Phylum",
        "class": "Class",
        "order": "Order",
        "family": "Family",
        "genus": "Genus",
        "iucnRedListCategory": "IUCN Status (code)",
        "iucnLabel": "IUCN Status",
        "establishmentMeans": "Establishment Means (code)",
        "establishmentLabel": "Establishment Means",
        "decimalLatitude": "Latitude",
        "decimalLongitude": "Longitude",
        "countryCode": "Country Code",
        "stateProvince": "State / Province",
        "locality": "Locality",
        "eventDate": "Date",
        "year": "Year",
        "month": "Month",
        "day": "Day",
        "basisOfRecord": "Basis of Record (code)",
        "observationType": "Observation Type",
        "individualCount": "Individual Count",
        "recordedBy": "Recorded By",
        "datasetName": "Dataset",
        "institutionCode": "Institution",
        "occurrenceID": "Occurrence ID",
        "gbifID": "GBIF ID",
    }

    available = {k: v for k, v in export_cols.items() if k in df.columns}
    export_df = df[list(available.keys())].copy()
    export_df.columns = list(available.values())
    return export_df
