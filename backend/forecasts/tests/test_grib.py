from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
import numpy as np

from forecasts.pipeline.grib import ForecastFieldError, read_precipitation_field


class GribDecodingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import eccodes
        except ImportError as error:
            raise RuntimeError("ecCodes is required for GRIB parser tests") from error
        cls.eccodes = eccodes

    def make_fixture(self, target: Path):
        ec = self.eccodes
        handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        try:
            for key, value in (
                ("shortName", "tp"),
                ("Ni", 1440),
                ("Nj", 721),
                ("latitudeOfFirstGridPointInDegrees", 90.0),
                ("longitudeOfFirstGridPointInDegrees", 0.0),
                ("iDirectionIncrementInDegrees", 0.25),
                ("jDirectionIncrementInDegrees", 0.25),
                ("dataDate", 20261114),
                ("dataTime", 0),
                ("startStep", 0),
                ("endStep", 24),
                ("stepType", "accum"),
            ):
                ec.codes_set(handle, key, value)
            ec.codes_set_values(handle, np.zeros(1440 * 721, dtype=np.float64))
            with target.open("wb") as output:
                ec.codes_write(handle, output)
        finally:
            ec.codes_release(handle)

    def test_decodes_valid_global_tp_and_checks_run_times(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.grib2"
            self.make_fixture(path)

            field = read_precipitation_field(path, 24, datetime(2026, 11, 14, tzinfo=timezone.utc))

        self.assertEqual(field.values.size, 1440 * 721)
        self.assertEqual(field.metadata["shortName"], "tp")
        self.assertEqual(field.grid.precipitation_to_mm, 1000)

    def test_rejects_a_field_from_the_wrong_initialization(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.grib2"
            self.make_fixture(path)

            with self.assertRaises(ForecastFieldError):
                read_precipitation_field(path, 24, datetime(2026, 11, 14, 12, tzinfo=timezone.utc))
