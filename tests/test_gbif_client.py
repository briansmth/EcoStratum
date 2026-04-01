"""Tests for modules/gbif_client.py — unit tests with mocked API calls."""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from modules.gbif_client import (
    point_to_bbox,
    get_iucn_threatened,
    get_invasive_species,
    build_detailed_csv,
)


class TestPointToBbox:
    def test_equator(self):
        bbox = point_to_bbox(0.0, 0.0, 10.0)
        assert "decimalLatitude" in bbox
        assert "decimalLongitude" in bbox
        lat_range = bbox["decimalLatitude"].split(",")
        assert float(lat_range[0]) < 0 < float(lat_range[1])

    def test_high_latitude(self):
        bbox = point_to_bbox(60.0, 10.0, 5.0)
        lon_range = bbox["decimalLongitude"].split(",")
        # At 60 degrees, longitude buffer should be wider than latitude buffer
        lat_range = bbox["decimalLatitude"].split(",")
        lat_span = float(lat_range[1]) - float(lat_range[0])
        lon_span = float(lon_range[1]) - float(lon_range[0])
        assert lon_span > lat_span

    def test_symmetry(self):
        bbox = point_to_bbox(46.95, 7.45, 10.0)
        lat_range = bbox["decimalLatitude"].split(",")
        center = (float(lat_range[0]) + float(lat_range[1])) / 2
        assert abs(center - 46.95) < 0.001


class TestGetIucnThreatened:
    def test_filters_threatened(self):
        df = pd.DataFrame({
            "species": ["A", "B", "C", "D"],
            "iucn_status": ["CR", "LC", "EN", "VU"],
        })
        result = get_iucn_threatened(df)
        assert len(result) == 3
        assert "B" not in result["species"].values

    def test_includes_near_threatened(self):
        df = pd.DataFrame({
            "species": ["A"],
            "iucn_status": ["NT"],
        })
        result = get_iucn_threatened(df)
        assert len(result) == 1

    def test_empty(self):
        result = get_iucn_threatened(pd.DataFrame())
        assert result.empty


class TestGetInvasiveSpecies:
    def test_filters_invasive(self):
        df = pd.DataFrame({
            "species": ["A", "B", "C"],
            "establishment": ["INVASIVE", "NATIVE", "INTRODUCED"],
        })
        result = get_invasive_species(df)
        assert len(result) == 2

    def test_empty(self):
        result = get_invasive_species(pd.DataFrame())
        assert result.empty


class TestBuildDetailedCsv:
    def test_column_renaming(self):
        df = pd.DataFrame({
            "scientificName": ["Vulpes vulpes"],
            "vernacularName": ["Red Fox"],
            "kingdom": ["Animalia"],
            "decimalLatitude": [46.95],
            "decimalLongitude": [7.45],
            "eventDate": ["2023-01-01"],
            "individualCount": ["1"],
        })
        result = build_detailed_csv(df)
        assert "Scientific Name" in result.columns
        assert "Common Name" in result.columns
        assert "Individual Count" in result.columns

    def test_empty(self):
        result = build_detailed_csv(pd.DataFrame())
        assert result.empty
