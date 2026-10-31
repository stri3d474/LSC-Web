"""Safe model-package zip inspection (C2).

SECURITY(MODEL-02): protects against zip-slip (path traversal via entry names)
and decompression bombs (oversized or too-many entries, excessive compression
ratio). Nothing is extracted to disk; entries are read into bounded in-memory
buffers for hashing and the manifest is parsed from memory.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass

from lsc_api.core.errors import ValidationError

# Decompression-bomb guards.
_MAX_ENTRIES = 32
_MAX_TOTAL_UNCOMPRESSED = 256 * 1024 * 1024  # 256 MiB across all entries
_MAX_SINGLE_UNCOMPRESSED = 128 * 1024 * 1024  # 128 MiB per entry
_MAX_RATIO = 200  # uncompressed:compressed per entry


@dataclass(frozen=True)
class PackageContents:
    """In-memory view of a validated package zip."""

    # name -> raw bytes for every entry (bounded by the guards above).
    entries: dict[str, bytes]

    def get(self, name: str) -> bytes | None:
        return self.entries.get(name)

    def sha256(self, name: str) -> str | None:
        data = self.entries.get(name)
        return hashlib.sha256(data).hexdigest() if data is not None else None


def _safe_entry_name(name: str) -> None:
    """Reject zip-slip and nested paths. Entries must be flat file names."""

    if name.endswith("/"):
        raise ValidationError("package must not contain directories")
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise ValidationError(f"unsafe entry name in package: {name!r}")
    if name.startswith("/") or ":" in name:
        raise ValidationError(f"unsafe entry name in package: {name!r}")


def read_package(zip_bytes: bytes) -> PackageContents:
    """Read a package zip into memory with bomb and zip-slip protections.

    Inputs: the raw zip bytes (already size-capped at the HTTP boundary).
    Outputs: :class:`PackageContents` mapping each flat entry name to its bytes.
    Failure modes: ``ValidationError`` if the zip is invalid, has unsafe entry
    names, or trips a decompression-bomb guard. Nothing is written to disk.
    """

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ValidationError("package is not a valid zip") from exc

    infos = zf.infolist()
    if len(infos) > _MAX_ENTRIES:
        raise ValidationError("package has too many entries")

    total = 0
    entries: dict[str, bytes] = {}
    for info in infos:
        _safe_entry_name(info.filename)
        if info.file_size > _MAX_SINGLE_UNCOMPRESSED:
            raise ValidationError(f"entry too large: {info.filename!r}")
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > _MAX_RATIO:
                raise ValidationError(f"suspicious compression ratio: {info.filename!r}")
        total += info.file_size
        if total > _MAX_TOTAL_UNCOMPRESSED:
            raise ValidationError("package uncompressed size exceeds limit")

        # Read with an explicit cap so a lying header cannot overrun memory.
        with zf.open(info, "r") as handle:
            data = handle.read(_MAX_SINGLE_UNCOMPRESSED + 1)
        if len(data) > _MAX_SINGLE_UNCOMPRESSED:
            raise ValidationError(f"entry exceeded declared size: {info.filename!r}")
        entries[info.filename] = data

    return PackageContents(entries=entries)
