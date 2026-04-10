"""Structured logging support for MultiTrust."""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str = "multitrust") -> Any:
    """Get a structured logger.

    Uses structlog if available, falls back to stdlib logging.
    """
    try:
        import structlog  # type: ignore[import-untyped]

        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)
