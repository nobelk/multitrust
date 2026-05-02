"""Smoke tests for the example scripts.

Each example script has a top-level ``main()`` coroutine that exercises the
public API end-to-end. The tests below import each example as a module
(catches syntax/import regressions) and ``await main()`` (catches behavior
regressions). They keep ``examples/`` honest as the docs and cookbook link
to it as the canonical runnable form.

Tied to Phase 1 validation: ``specs/2026-05-02-adoption-onboarding/validation.md``
"Examples smoke run" — every example listed there must round-trip cleanly.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"

EXAMPLE_MODULES = [
    "quickstart",
    "multi_source_fusion",
    "trust_decay",
    "authority_discounting",
]


def _load_main(name: str) -> Callable[[], Awaitable[Any]]:
    """Load an example and return its ``main`` coroutine factory."""
    path = EXAMPLES_DIR / f"{name}.py"
    if not path.exists():
        pytest.skip(f"example {name}.py not yet present")
    spec = importlib.util.spec_from_file_location(f"examples.{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    main = getattr(module, "main", None)
    assert callable(main), f"examples/{name}.py must expose a top-level main()"
    return main  # type: ignore[no-any-return]


@pytest.mark.parametrize("name", EXAMPLE_MODULES)
async def test_example_runs(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    main = _load_main(name)
    await main()

    captured = capsys.readouterr()
    assert captured.out.strip(), f"examples/{name}.py produced no output"
