"""
solfa_spec.py - Tonic Solfa Notation Spec Loader (Python)
==========================================================

Loads solfadoc-spec.yaml and exposes it as a plain dict.
This is the single source of truth for all notation constants in Python.

Usage:
    from shared import spec

    spec["notes"]["solfa_to_semitone"]    # dict: {"d": 0, "r": 2, ...}
    spec["rhythm"]["soft_barline"]        # dict with char, rules etc.
    spec["voices"]["voice_config"]["S"]   # dict: name, clef, octave_offset ...
    spec["dynamics"]["valid_dynamics"]    # list: ["ppp", "pp", ...]
    spec["lyrics"]["refrain_token"]       # "R"

The YAML file is located at:
    - Same directory as this script (development)
    - Package resources (installed)

Do NOT import from config.py for new code - import from this module.
config.py is kept only as a backward-compatibility shim.
"""

import importlib.resources
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_SPEC_FILENAME = "solfadoc-spec.yaml"

def _find_spec_file() -> Path:
    """
    Locate solfadoc-spec.yaml. Search order:
      1. Directory of this script (development / editable install)
      2. Package resources (installed via pip)
    """
    # 1. Repository root (development / editable install)
    repo_root = Path(__file__).parent.parent.parent / _SPEC_FILENAME
    if repo_root.exists():
        return repo_root

    # 2. Same directory as this script (fallback)
    local = Path(__file__).parent / _SPEC_FILENAME
    if local.exists():
        return local

    # 3. Installed package - look in package resources
    try:
        ref = importlib.resources.files(__package__ or "solfa_spec") / _SPEC_FILENAME
        with importlib.resources.as_file(ref) as path:
            if path.exists():
                return path
    except (TypeError, FileNotFoundError, AttributeError):
        pass

    raise FileNotFoundError(
        "solfadoc-spec.yaml not found. "
        "Expected alongside solfa_spec.py or in package resources."
    )


def _load() -> dict[str, Any]:
    path = _find_spec_file()
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"solfadoc-spec.yaml root must be a YAML mapping, got: {type(data).__name__}"
        )

    _assert_version(data)
    _build_derived(data)
    return data


def _assert_version(data: dict) -> None:
    version = data.get("meta", {}).get("spec_version", "")
    if version and not str(version).startswith("2"):
        raise ValueError(
            f"Unsupported solfadoc-spec version: {version}. "
            "This loader requires spec_version 2.x"
        )


def _build_derived(data: dict) -> None:
    """
    Add derived / combined structures that are useful at runtime but
    would be redundant to maintain manually in the YAML.
    """
    notes = data.get("notes", {})

    # Combined all-notes dict: chromatic_sharp + chromatic_flat + solfa_to_semitone
    combined: dict[str, int] = {}
    combined.update(notes.get("chromatic_sharp", {}))
    combined.update(notes.get("chromatic_flat", {}))
    combined.update(notes.get("solfa_to_semitone", {}))
    notes["all_notes"] = combined

    # Tokens sorted longest-first for greedy matching / regex alternation
    notes["tokens_sorted"] = sorted(combined.keys(), key=len, reverse=True)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_spec: dict[str, Any] | None = None


def _get_spec() -> dict[str, Any] | None:
    global _spec
    if _spec is None:
        _spec = _load()
    return _spec


class _SpecProxy:
    """
    Thin proxy so callers can write  spec["notes"]  or  spec.notes
    without importing a global dict directly (easier to mock in tests).
    """
    def __getitem__(self, key: str) -> Any:
        return _get_spec()[key]

    def __getattr__(self, key: str) -> Any:
        try:
            return _get_spec()[key]
        except KeyError:
            raise AttributeError(f"solfadoc-spec has no section '{key}'")

    def reload(self) -> None:
        """Force a reload - useful in tests or when the YAML changes on disk."""
        global _spec
        _spec = None
        _get_spec()


spec: _SpecProxy = _SpecProxy()


# ---------------------------------------------------------------------------
# Convenience helpers (mirror the most common config.py accesses)
# ---------------------------------------------------------------------------

def all_notes() -> dict[str, int]:
    """All solfa tokens (natural + chromatic) → semitone offset from do."""
    return spec["notes"]["all_notes"]


def tokens_sorted() -> list[str]:
    """All solfa tokens sorted longest-first for greedy matching."""
    return spec["notes"]["tokens_sorted"]


def valid_dynamics() -> list[str]:
    """List of valid dynamic mark strings."""
    return spec["dynamics"]["valid_dynamics"]


def valid_keys() -> list[str]:
    """List of valid key signature strings."""
    return spec["keys"]["valid_keys"]


def navigation_markers() -> dict[str, str]:
    """Map of navigation marker keywords → display text."""
    return spec["navigation"]["markers"]


def voice_labels() -> list[str]:
    """All defined voice/part labels."""
    return list(spec["voices"]["voice_config"].keys())


def instrument_parts() -> list[str]:
    """Instrument part labels that cannot carry lyrics."""
    return spec["voices"]["instrument_parts"]
