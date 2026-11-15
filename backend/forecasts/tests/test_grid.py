from django.test import SimpleTestCase
import numpy as np

from forecasts.pipeline.grid import (
    GridMetadataError,
    cache_key,
    interval_precipitation,
    render_precipitation_tile,
    validate_forecast_metadata,
)


class ForecastMetadataTests(SimpleTestCase):
    def setUp(self):
        self.metadata = {
            "shortName": "tp",
            "units": "m",
            "stepType": "accum",
            "typeOfLevel": "surface",
            "startStep": 0,
            "endStep": 24,
            "gridType": "regular_ll",
            "Ni": 1440,
            "Nj": 721,
            "latitudeOfFirstGridPointInDegrees": 90.0,
            "longitudeOfFirstGridPointInDegrees": 0.0,
            "iDirectionIncrementInDegrees": 0.25,
            "jDirectionIncrementInDegrees": 0.25,
            "iScansNegatively": 0,
            "jScansPositively": 0,
            "jPointsAreConsecutive": 0,
            "alternativeRowScanning": 0,
        }

    def test_accepts_expected_global_accumulation(self):
        grid = validate_forecast_metadata(self.metadata, lead_hours=24)

        self.assertEqual((grid.width, grid.height), (1440, 721))
        self.assertAlmostEqual(grid.precipitation_to_mm, 1000.0)

    def test_accepts_global_grid_with_180_degree_longitude_origin(self):
        metadata = {**self.metadata, "longitudeOfFirstGridPointInDegrees": 180.0}

        grid = validate_forecast_metadata(metadata, lead_hours=24)

        self.assertEqual(grid.first_longitude, 180.0)

    def test_rejects_wrong_parameter_units_or_step(self):
        for key, value in (("shortName", "2t"), ("units", "kg m-2"), ("endStep", 12)):
            with self.subTest(key=key):
                metadata = {**self.metadata, key: value}
                with self.assertRaises(GridMetadataError):
                    validate_forecast_metadata(metadata, lead_hours=24)

    def test_rejects_unhandled_grid_scanning(self):
        metadata = {**self.metadata, "jPointsAreConsecutive": 1}

        with self.assertRaises(GridMetadataError):
            validate_forecast_metadata(metadata, lead_hours=24)

    def test_cache_key_changes_for_each_data_or_processing_dimension(self):
        base = {
            "run": "ifs-oper-0p25-20261114T00Z-t24",
            "source_sha256": "a" * 64,
            "parameter": "tp",
            "lead_hours": 24,
            "z": 5,
            "x": 17,
            "y": 12,
            "processing_version": "v1",
        }
        original = cache_key(base)

        for key, value in (("run", "another-run"), ("source_sha256", "b" * 64),
                           ("parameter", "2t"), ("lead_hours", 48), ("z", 6),
                           ("x", 18), ("y", 13), ("processing_version", "v2")):
            with self.subTest(key=key):
                self.assertNotEqual(original, cache_key({**base, key: value}))

    def test_interval_difference_zeros_packing_noise_and_rejects_material_negative(self):
        values, valid = interval_precipitation(
            np.array([0.0100, 0.0200, 0.0300]),
            np.array([0.0101, 0.0190, 0.0320]),
            previous_error_m=0.0002,
            current_error_m=0.0002,
        )

        self.assertEqual(values[0], 0.0)
        self.assertFalse(valid[1])
        self.assertTrue(np.isnan(values[1]))
        self.assertAlmostEqual(values[2], 2.0)

    def test_precipitation_render_preserves_distinct_classes_and_transparent_zero_or_missing(self):
        from io import BytesIO
        from PIL import Image

        values = np.array([[0.0, 0.5, 3.0, np.nan]])
        image = Image.open(BytesIO(render_precipitation_tile(values))).convert("RGBA")

        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertEqual(image.getpixel((1, 0)), (187, 222, 251, 180))
        self.assertEqual(image.getpixel((2, 0)), (30, 136, 229, 205))
        self.assertEqual(image.getpixel((3, 0))[3], 0)
