"""Coverage for the OPS_LOGGING_PATH override semantics in
visibility/visibility/_obs.py (and by symmetry app/_obs.py — the body of
the two files is identical past the path-resolution step).

Three behaviors:
  1. OPS_LOGGING_PATH set + valid → imports the real middleware module
  2. OPS_LOGGING_PATH set + invalid → RuntimeError with the bad path in
     the message and the original ImportError chained
  3. OPS_LOGGING_PATH unset + bogus default → silent stdlib fallback;
     module imports without raising; CorrelationIdMiddleware is a no-op
     ASGI shim

We re-import a fresh copy of _obs per case via importlib so each test
gets a clean module-load.
"""
from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import pytest


def _purge_obs_modules() -> None:
    """Drop _obs (and the shared `middleware` module it imports) from
    sys.modules so the next import re-executes the bootstrap."""
    for name in ("visibility._obs", "middleware"):
        sys.modules.pop(name, None)


def _purge_sys_path(needle: str) -> None:
    """Strip any sys.path entry containing `needle` so a bogus override
    isn't accidentally rescued by a prior leak."""
    sys.path[:] = [p for p in sys.path if needle not in p]


@pytest.fixture(autouse=True)
def restore_state():
    """Snapshot sys.path + sys.modules state and restore after each test —
    these tests poke globals on purpose; isolation matters."""
    saved_path = list(sys.path)
    saved_modules = {
        k: v for k, v in sys.modules.items() if k in ("visibility._obs", "middleware")
    }
    yield
    sys.path[:] = saved_path
    for k in ("visibility._obs", "middleware"):
        sys.modules.pop(k, None)
    for k, v in saved_modules.items():
        sys.modules[k] = v


def test_valid_override_loads_real_middleware(monkeypatch) -> None:
    real = str(
        Path(__file__).resolve().parents[2] / "ops" / "logging" / "python"
    )
    monkeypatch.setenv("OPS_LOGGING_PATH", real)
    _purge_obs_modules()
    mod = importlib.import_module("visibility._obs")
    # When the real middleware loads, configure_structlog has structlog
    # plumbing — its module path will be `middleware`, not the local
    # fallback shim defined inside _obs.
    assert mod.configure_structlog.__module__ == "middleware"
    assert mod.CorrelationIdMiddleware.__module__ == "middleware"


def test_bogus_override_raises_runtime_error_with_path(monkeypatch, tmp_path) -> None:
    bogus = str(tmp_path / "no-such-dir")
    monkeypatch.setenv("OPS_LOGGING_PATH", bogus)
    _purge_obs_modules()
    # Make sure no other entry on sys.path can rescue the import.
    _purge_sys_path("ops/logging/python")

    with pytest.raises(RuntimeError) as exc_info:
        importlib.import_module("visibility._obs")

    msg = str(exc_info.value)
    assert bogus in msg, f"path not in error: {msg!r}"
    assert "OPS_LOGGING_PATH" in msg
    # Original cause is chained for forensics.
    assert isinstance(exc_info.value.__cause__, ImportError)


def test_unset_env_with_bogus_relative_path_falls_back(monkeypatch, tmp_path) -> None:
    """When OPS_LOGGING_PATH is unset AND the in-tree default can't be
    imported, we silently fall back to stdlib. Models the local-dev case
    where someone runs the service from a checkout without the ops/ tree."""
    monkeypatch.delenv("OPS_LOGGING_PATH", raising=False)
    _purge_obs_modules()
    # Strip the real ops path so the in-tree default doesn't accidentally
    # win, then also patch the file location so the bootstrap thinks the
    # default points at an empty directory.
    _purge_sys_path("ops/logging/python")

    # Use a temp file-stand-in so the relative-path computation lands in a
    # directory with no `middleware.py`. We patch __file__ on the loaded
    # module before import by writing a sibling file and pointing the
    # importer at it.
    fake_root = tmp_path / "fake_visibility" / "visibility"
    fake_root.mkdir(parents=True)
    fake_obs = fake_root / "_obs.py"
    real_src = (
        Path(__file__).resolve().parents[1] / "visibility" / "_obs.py"
    )
    fake_obs.write_text(real_src.read_text())
    (fake_root / "__init__.py").write_text("")
    (fake_root.parent / "__init__.py").write_text("")
    sys.path.insert(0, str(tmp_path))
    sys.modules.pop("fake_visibility", None)
    sys.modules.pop("fake_visibility.visibility", None)
    sys.modules.pop("fake_visibility.visibility._obs", None)

    mod = importlib.import_module("fake_visibility.visibility._obs")
    # Fallback shim: CorrelationIdMiddleware is defined inside _obs itself.
    assert mod.CorrelationIdMiddleware.__module__.endswith("_obs")
    # configure_structlog is the stdlib-only no-op (its module is also _obs).
    assert mod.configure_structlog.__module__.endswith("_obs")
    # And it doesn't blow up when actually invoked.
    mod.configure_structlog("test-service")
    assert isinstance(mod.get_logger("x"), logging.Logger)
