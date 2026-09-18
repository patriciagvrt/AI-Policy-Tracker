"""Project configuration loading.

Everything that varies between environments or runs (file paths, collector
politeness settings, the BERTopic embedding model name, and so on) lives in
config/settings.yaml rather than being hard-coded in the pipeline modules.
This module is the one place that reads that YAML file, so the rest of the
codebase can just call `get_settings()` and trust the result.

Written for a learner: `functools.lru_cache` here just means "run this
function once, then remember the answer" -- so re-reading settings.yaml
100 times during a pipeline run doesn't cost 100 disk reads.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# The repository root is three levels up from this file:
# src/nordic_ai_policy_tracker/config.py -> src/nordic_ai_policy_tracker -> src -> <root>
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


@lru_cache(maxsize=1)
def get_settings(settings_path: str | Path | None = None) -> dict[str, Any]:
    """Load config/settings.yaml and return it as a nested dict.

    Args:
        settings_path: Optional override path, mainly used by tests so they
            can point at a fixture settings file instead of the real one.

    Returns:
        The parsed YAML content as a dictionary.

    Raises:
        FileNotFoundError: if the settings file does not exist.
    """
    path = Path(settings_path) if settings_path else DEFAULT_SETTINGS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Settings file not found at {path}. "
            "Did you run this from the project root, or pass settings_path?"
        )
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_path(relative_path: str) -> Path:
    """Turn a path from settings.yaml (relative to the repo root) into an
    absolute Path object.
    """
    return REPO_ROOT / relative_path


def get_coding_dimensions(settings_path: str | Path | None = None) -> dict[str, Any]:
    """Load config/coding_dimensions.yaml.

    Kept separate from get_settings() because the coding dimensions file is
    conceptually a research artifact (the operationalized framework), not a
    runtime setting -- and code that only needs settings shouldn't have to
    also load the (larger) dimensions file.
    """
    settings = get_settings(settings_path)
    dims_path = resolve_path(settings["paths"]["coding_dimensions_yaml"])
    with dims_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
