import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from forecasts.pipeline.cache import cached_tile, get_or_create_source, get_or_create_tile


@override_settings(FORECAST_SOURCE_CACHE_TTL_SECONDS=60, FORECAST_TILE_CACHE_TTL_SECONDS=60)
class FileCacheTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(FORECAST_CACHE_DIR=self.tempdir.name)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.tempdir.cleanup()

    def test_source_is_downloaded_once_for_sequential_requests(self):
        downloads = []

        def downloader(target: Path):
            downloads.append(True)
            target.write_bytes(b"source payload")

        first = get_or_create_source("run-sequential", downloader)
        second = get_or_create_source("run-sequential", downloader)

        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        self.assertTrue(first[2])
        self.assertFalse(second[2])
        self.assertEqual(len(downloads), 1)

    def test_concurrent_misses_share_one_download(self):
        count = 0
        guard = threading.Lock()

        def downloader(target: Path):
            nonlocal count
            with guard:
                count += 1
            time.sleep(0.05)
            target.write_bytes(b"one source")

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: get_or_create_source("run-concurrent", downloader), range(4)))

        self.assertEqual(count, 1)
        self.assertEqual(len({result[1] for result in results}), 1)

    def test_tiles_are_cached_and_png_validated(self):
        calls = []

        def renderer():
            calls.append(True)
            return b"\x89PNG\r\n\x1a\nfixture"

        first = get_or_create_tile("a" * 64, renderer)
        second = get_or_create_tile("a" * 64, renderer)

        self.assertTrue(first[1])
        self.assertFalse(second[1])
        self.assertEqual(len(calls), 1)
        self.assertTrue(first[0].is_file())

    def test_expired_sources_are_downloaded_again(self):
        calls = []

        def downloader(target: Path):
            calls.append(True)
            target.write_bytes(f"source-{len(calls)}".encode())

        first = get_or_create_source("run-expired", downloader)
        old = time.time() - 120
        os.utime(first[0], (old, old))
        second = get_or_create_source("run-expired", downloader)

        self.assertEqual(len(calls), 2)
        self.assertNotEqual(first[1], second[1])

    @override_settings(FORECAST_TILE_CACHE_TTL_SECONDS=120)
    def test_source_expiry_does_not_expire_or_extend_a_tile(self):
        source_calls = []

        def downloader(target: Path):
            source_calls.append(True)
            target.write_bytes(f"bundle-{len(source_calls)}".encode())

        source, _, _ = get_or_create_source("run-independent-ttl", downloader)
        tile, _ = get_or_create_tile("b" * 64, lambda: b"\x89PNG\r\n\x1a\nfixture")
        old = time.time() - 70
        os.utime(source, (old, old))
        os.utime(tile, (old, old))

        renewed_source = get_or_create_source("run-independent-ttl", downloader)
        still_cached_tile = cached_tile("b" * 64)

        self.assertTrue(renewed_source[2])
        self.assertEqual(len(source_calls), 2)
        self.assertEqual(still_cached_tile, tile)
        self.assertEqual(int(tile.stat().st_mtime), int(old))
