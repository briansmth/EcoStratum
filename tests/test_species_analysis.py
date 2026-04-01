"""Tests for modules/species_analysis.py"""

import pandas as pd
import pytest
from modules.species_analysis import (
    compute_overview_stats,
    species_by_group,
    observations_by_year,
    iucn_breakdown,
    top_species,
)


@pytest.fixture
def sample_raw_df():
    return pd.DataFrame({
        "species": ["Vulpes vulpes", "Vulpes vulpes", "Aquila chrysaetos", "Bufo bufo"],
        "scientificName": ["Vulpes vulpes", "Vulpes vulpes", "Aquila chrysaetos", "Bufo bufo"],
        "kingdom": ["Animalia"] * 4,
        "class": ["Mammalia", "Mammalia", "Aves", "Amphibia"],
        "order": ["Carnivora", "Carnivora", "Accipitriformes", "Anura"],
        "family": ["Canidae", "Canidae", "Accipitridae", "Bufonidae"],
        "year": [2020, 2021, 2022, 2023],
        "decimalLatitude": [46.95, 46.96, 46.97, 46.98],
        "decimalLongitude": [7.45, 7.46, 7.47, 7.48],
        "eventDate": ["2020-06-01", "2021-07-15", "2022-03-10", "2023-05-20"],
        "iucnRedListCategory": ["LC", "LC", "LC", "LC"],
        "iucnLabel": ["Least Concern"] * 4,
        "establishmentMeans": ["NATIVE", "NATIVE", "", "INTRODUCED"],
        "establishmentLabel": ["Native", "Native", "", "Introduced"],
        "individualCount": ["1", "2", "1", "3"],
        "basisOfRecord": ["HUMAN_OBSERVATION"] * 4,
        "observationType": ["Direct observation (visual)"] * 4,
        "vernacularName": ["Red Fox", "Red Fox", "Golden Eagle", "Common Toad"],
    })


@pytest.fixture
def sample_summary_df():
    return pd.DataFrame({
        "species": ["Vulpes vulpes", "Aquila chrysaetos", "Bufo bufo"],
        "kingdom": ["Animalia"] * 3,
        "phylum": ["Chordata"] * 3,
        "class": ["Mammalia", "Aves", "Amphibia"],
        "order": ["Carnivora", "Accipitriformes", "Anura"],
        "family": ["Canidae", "Accipitridae", "Bufonidae"],
        "observation_count": [2, 1, 1],
        "iucn_status": ["LC", "LC", "LC"],
        "iucn_label": ["Least Concern"] * 3,
        "establishment": ["NATIVE", "", "INTRODUCED"],
        "establishment_label": ["Native", "", "Introduced"],
        "common_name": ["Red Fox", "Golden Eagle", "Common Toad"],
        "first_observed": [2020, 2022, 2023],
        "last_observed": [2021, 2022, 2023],
    })


class TestComputeOverviewStats:
    def test_basic_stats(self, sample_raw_df, sample_summary_df):
        stats = compute_overview_stats(sample_raw_df, sample_summary_df)
        assert stats["total_observations"] == 4
        assert stats["unique_species"] == 3
        assert stats["taxonomic_groups"] == 3
        assert stats["date_range"] == "2020-2023"

    def test_empty_dataframes(self):
        stats = compute_overview_stats(pd.DataFrame(), pd.DataFrame())
        assert stats["total_observations"] == 0
        assert stats["unique_species"] == 0
        assert stats["date_range"] == "N/A"

    def test_threatened_count(self):
        summary = pd.DataFrame({
            "species": ["A", "B", "C"],
            "class": ["Aves"] * 3,
            "iucn_status": ["CR", "EN", "LC"],
            "establishment": ["", "", ""],
        })
        raw = pd.DataFrame({"species": ["A", "B", "C"], "year": [2020, 2021, 2022]})
        stats = compute_overview_stats(raw, summary)
        assert stats["threatened_count"] == 2

    def test_invasive_count(self):
        summary = pd.DataFrame({
            "species": ["A", "B"],
            "class": ["Aves"] * 2,
            "iucn_status": ["LC", "LC"],
            "establishment": ["INVASIVE", "NATIVE"],
        })
        raw = pd.DataFrame({"species": ["A", "B"], "year": [2020, 2021]})
        stats = compute_overview_stats(raw, summary)
        assert stats["invasive_count"] == 1


class TestSpeciesByGroup:
    def test_groups(self, sample_summary_df):
        result = species_by_group(sample_summary_df)
        assert len(result) == 3
        assert "species_count" in result.columns

    def test_empty(self):
        result = species_by_group(pd.DataFrame())
        assert result.empty


class TestObservationsByYear:
    def test_timeline(self, sample_raw_df):
        result = observations_by_year(sample_raw_df)
        assert len(result) == 4
        assert result["year"].dtype == int

    def test_empty(self):
        result = observations_by_year(pd.DataFrame())
        assert result.empty


class TestIucnBreakdown:
    def test_breakdown(self, sample_summary_df):
        result = iucn_breakdown(sample_summary_df)
        assert "category" in result.columns
        assert "label" in result.columns

    def test_empty(self):
        result = iucn_breakdown(pd.DataFrame())
        assert result.empty


class TestTopSpecies:
    def test_top_n(self, sample_summary_df):
        result = top_species(sample_summary_df, n=2)
        assert len(result) == 2
        assert result.iloc[0]["observation_count"] >= result.iloc[1]["observation_count"]

    def test_empty(self):
        result = top_species(pd.DataFrame())
        assert result.empty
