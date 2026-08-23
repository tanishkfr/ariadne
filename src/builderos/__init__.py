"""Builder OS user-local product launcher."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path


def package_version() -> str:
    """Return installed metadata, or the source-tree VERSION during development."""
    try:
        return metadata.version("builder-os")
    except metadata.PackageNotFoundError:
        source_version = Path(__file__).resolve().parents[2] / "VERSION"
        return source_version.read_text(encoding="utf-8").strip() if source_version.is_file() else "unknown"


__version__ = package_version()
