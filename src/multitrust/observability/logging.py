"""Structured logging support for MultiTrust via OpenTelemetry."""

from __future__ import annotations

import atexit
import logging
from typing import Any

_otel_handler_installed = False
_otel_provider: Any = None


def _ensure_otel_handler(logger: logging.Logger) -> None:
    """Attach the OTel LoggingHandler to *logger* once (if the SDK is available)."""
    global _otel_handler_installed, _otel_provider  # noqa: PLW0603
    if _otel_handler_installed:
        return

    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import (
            ConsoleLogExporter,
            SimpleLogRecordProcessor,
        )

        provider = LoggerProvider()
        provider.add_log_record_processor(SimpleLogRecordProcessor(ConsoleLogExporter()))
        set_logger_provider(provider)

        handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
        logger.addHandler(handler)
        _otel_provider = provider
        _otel_handler_installed = True

        atexit.register(_shutdown_otel)
    except ImportError:
        pass


def _shutdown_otel() -> None:
    """Flush and shut down the OTel LoggerProvider before interpreter teardown."""
    if _otel_provider is not None:
        _otel_provider.shutdown()


def get_logger(name: str = "multitrust") -> Any:
    """Get a logger that emits records through OpenTelemetry when available.

    Resolution order:
      1. stdlib logger + OTel ``LoggingHandler`` (if ``opentelemetry-sdk`` installed)
      2. structlog (if installed, wrapping the stdlib logger)
      3. plain stdlib logger
    """
    stdlib_logger = logging.getLogger(name)

    _ensure_otel_handler(stdlib_logger)
    if _otel_handler_installed:
        return stdlib_logger

    try:
        import structlog

        return structlog.get_logger(name)
    except ImportError:
        return stdlib_logger
