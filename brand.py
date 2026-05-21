# brand.py — application name and data-directory paths
from __future__ import annotations

from pathlib import Path

APP_NAME = "text-seeker"
APP_TITLE = "text-seeker"
CLI_PROG = "text-seeker"

INDEX_DIR_NAME = ".text-seeker_index"
CACHE_DIR_NAME = ".text-seeker_cache"
LEGACY_INDEX_DIR_NAME = ".docseeker_index"
LEGACY_CACHE_DIR_NAME = ".docseeker_cache"


def default_index_dir() -> Path:
    return Path.home() / INDEX_DIR_NAME


def default_cache_dir() -> Path:
    return Path.home() / CACHE_DIR_NAME


def legacy_index_dirs() -> list[Path]:
    return [Path.home() / LEGACY_INDEX_DIR_NAME]


def legacy_cache_dirs() -> list[Path]:
    return [Path.home() / LEGACY_CACHE_DIR_NAME]
