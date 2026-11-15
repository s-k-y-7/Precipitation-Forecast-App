"""Atomic, bounded-lifetime filesystem caches shared by backend workers."""

from __future__ import annotations

import fcntl
import hashlib
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from django.conf import settings


class CacheError(RuntimeError):
    pass


def cache_root() -> Path:
    root = Path(settings.FORECAST_CACHE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_path(run_id: str) -> Path:
    return cache_root() / "sources" / f"{_token(run_id)}.grib2"


def tile_path(key: str) -> Path:
    return cache_root() / "tiles" / key[:2] / f"{key}.png"


def _fresh(path: Path, ttl_seconds: int) -> bool:
    try:
        if not path.is_file():
            return False
        if time.time() - path.stat().st_mtime <= ttl_seconds:
            return True
        path.unlink(missing_ok=True)
        return False
    except FileNotFoundError:
        return False


def cached_tile(key: str) -> Path | None:
    path = tile_path(key)
    with _file_lock(path.with_suffix(".lock")):
        return path if _fresh(path, settings.FORECAST_CACHE_TTL_SECONDS) else None


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def get_or_create_source(run_id: str, downloader: Callable[[Path], None]) -> tuple[Path, str, bool]:
    """Return (path, SHA-256, was_downloaded), deduplicating process workers."""
    destination = source_path(run_id)
    ttl = settings.FORECAST_CACHE_TTL_SECONDS
    lock = destination.with_suffix(".lock")
    with _file_lock(lock):
        if _fresh(destination, ttl):
            return destination, _sha256(destination), False
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix="download-", suffix=".partial", dir=destination.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            downloader(temporary)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise CacheError("ECMWF returned an empty source file")
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    return destination, _sha256(destination), True


def get_or_create_tile(key: str, renderer: Callable[[], bytes]) -> tuple[Path, bool]:
    """Return a cached tile, generating it atomically once across workers."""
    destination = tile_path(key)
    ttl = settings.FORECAST_CACHE_TTL_SECONDS
    lock = destination.with_suffix(".lock")
    with _file_lock(lock):
        if _fresh(destination, ttl):
            return destination, False
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = renderer()
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise CacheError("Tile renderer did not return a PNG image")
        fd, temporary_name = tempfile.mkstemp(prefix="tile-", suffix=".partial", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(content)
            os.replace(temporary_name, destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
    return destination, True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_prune_lock = threading.Lock()
_last_prune = 0.0


def prune_expired_cache(force: bool = False) -> int:
    """Opportunistically remove expired data files, at most once per five minutes."""
    global _last_prune
    now = time.time()
    if not force and now - _last_prune < 300:
        return 0
    with _prune_lock:
        if not force and now - _last_prune < 300:
            return 0
        root = cache_root()
        removed = 0
        ttl = settings.FORECAST_CACHE_TTL_SECONDS
        for folder in (root / "sources", root / "tiles"):
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                try:
                    if path.suffix in {".grib2", ".png"} and path.is_file() and now - path.stat().st_mtime > ttl:
                        path.unlink(missing_ok=True)
                        removed += 1
                except FileNotFoundError:
                    continue
        _last_prune = now
        return removed
