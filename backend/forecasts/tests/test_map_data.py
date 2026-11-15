import math

from django.test import SimpleTestCase
import numpy as np

from forecasts.pipeline.grid import (
    GridMetadata,
    GridMetadataError,
    render_precipitation_tile,
    sample_xyz_tile,
)


class MapDataTests(SimpleTestCase):
    def test_sampling_honors_the_grib_longitude_origin(self):
        grid = GridMetadata(4, 3, 180.0, 90.0, 90.0, 90.0, 1000.0)
        values = np.arange(12, dtype=np.float64)
        tile = sample_xyz_tile(values, grid, 2, 2, 1)
        # This tile pixel is near 78E, 26N: with a 180E grid origin it maps to col 3, row 1.
        pixel_x = int(((78.0 + 180.0) / 360.0) * 4 * 256) - 2 * 256
        world_y = (1 - math.asinh(math.tan(math.radians(26.0))) / math.pi) / 2
        pixel_y = int(world_y * 4 * 256) - 1 * 256

        self.assertEqual(tile[pixel_y, pixel_x], 7000.0)

    def test_sample_rejects_mismatched_grid_shape(self):
        grid = GridMetadata(4, 3, 0.0, 90.0, 90.0, 90.0, 1000.0)
        with self.assertRaises(GridMetadataError):
            sample_xyz_tile(np.zeros(11), grid, 0, 0, 0)

    def test_tile_coordinates_are_validated(self):
        grid = GridMetadata(4, 3, 0.0, 90.0, 90.0, 90.0, 1000.0)
        with self.assertRaises(ValueError):
            sample_xyz_tile(np.zeros(12), grid, 2, 4, 0)

    def test_rendered_png_has_expected_dimensions_and_transparency(self):
        from PIL import Image
        from io import BytesIO

        result = render_precipitation_tile(np.full((256, 256), np.nan))
        image = Image.open(BytesIO(result))
        self.assertEqual(image.size, (256, 256))
        self.assertEqual(image.getpixel((0, 0))[3], 0)
