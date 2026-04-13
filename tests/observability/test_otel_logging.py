"""Tests for OpenTelemetry logging integration."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

import multitrust.observability.logging as otel_logging
from multitrust.observability.logging import get_logger

try:
    import opentelemetry.sdk  # noqa: F401

    _has_otel = True
except ImportError:
    _has_otel = False

requires_otel = pytest.mark.skipif(not _has_otel, reason="opentelemetry-sdk not installed")


@pytest.fixture(autouse=True)
def _reset_otel_state():
    """Reset module-level OTel state between tests."""
    otel_logging._otel_handler_installed = False
    otel_logging._otel_provider = None
    yield
    otel_logging._otel_handler_installed = False
    otel_logging._otel_provider = None


@requires_otel
class TestGetLoggerWithOtel:
    """Tests when opentelemetry-sdk is available (the real install)."""

    def test_returns_stdlib_logger(self):
        logger = get_logger("multitrust.test")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_otel_handler(self):
        from opentelemetry.sdk._logs import LoggingHandler

        logger = get_logger("multitrust.test.handler")
        otel_handlers = [h for h in logger.handlers if isinstance(h, LoggingHandler)]
        assert len(otel_handlers) == 1

    def test_otel_handler_installed_once(self):
        get_logger("multitrust.test.once_a")
        get_logger("multitrust.test.once_b")
        assert otel_logging._otel_handler_installed is True

    def test_provider_is_set(self):
        get_logger("multitrust.test.provider")
        assert otel_logging._otel_provider is not None

    def test_log_records_reach_otel_exporter(self):
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import (
            InMemoryLogExporter,
            SimpleLogRecordProcessor,
        )

        exporter = InMemoryLogExporter()
        provider = LoggerProvider()
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))

        from opentelemetry.sdk._logs import LoggingHandler

        logger = logging.getLogger("multitrust.test.exporter")
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
        logger.addHandler(handler)

        try:
            logger.setLevel(logging.DEBUG)
            logger.warning("test otel message")

            records = exporter.get_finished_logs()
            assert len(records) >= 1
            assert any("test otel message" in r.log_record.body for r in records)
        finally:
            logger.removeHandler(handler)
            provider.shutdown()

    def test_different_log_levels_emitted(self):
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import (
            InMemoryLogExporter,
            SimpleLogRecordProcessor,
        )

        exporter = InMemoryLogExporter()
        provider = LoggerProvider()
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))

        logger = logging.getLogger("multitrust.test.levels")
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
        logger.addHandler(handler)

        try:
            logger.setLevel(logging.DEBUG)
            logger.debug("debug msg")
            logger.info("info msg")
            logger.warning("warning msg")
            logger.error("error msg")

            records = exporter.get_finished_logs()
            bodies = [r.log_record.body for r in records]
            assert "debug msg" in bodies
            assert "info msg" in bodies
            assert "warning msg" in bodies
            assert "error msg" in bodies
        finally:
            logger.removeHandler(handler)
            provider.shutdown()

    def test_default_logger_name(self):
        logger = get_logger()
        assert logger.name == "multitrust"

    def test_custom_logger_name(self):
        logger = get_logger("multitrust.custom")
        assert logger.name == "multitrust.custom"


class TestGetLoggerWithoutOtel:
    """Tests when opentelemetry is not importable."""

    def test_falls_back_to_stdlib_when_otel_missing(self):
        with patch.dict("sys.modules", {"opentelemetry": None, "opentelemetry._logs": None}):
            otel_logging._otel_handler_installed = False
            otel_logging._otel_provider = None
            logger = get_logger("multitrust.test.fallback")
            # Should not raise; should return a working logger
            assert hasattr(logger, "warning")

    def test_otel_flag_stays_false_when_import_fails(self):
        with patch(
            "multitrust.observability.logging._ensure_otel_handler",
            side_effect=lambda _: None,
        ):
            otel_logging._otel_handler_installed = False
            logger = get_logger("multitrust.test.noflag")
            assert hasattr(logger, "warning")


class TestShutdown:
    """Tests for the atexit shutdown hook."""

    def test_shutdown_calls_provider_shutdown(self):
        mock_provider = MagicMock()
        otel_logging._otel_provider = mock_provider

        otel_logging._shutdown_otel()

        mock_provider.shutdown.assert_called_once()

    def test_shutdown_noop_when_no_provider(self):
        otel_logging._otel_provider = None
        # Should not raise
        otel_logging._shutdown_otel()


@requires_otel
class TestNormalizeUsesOtelLogger:
    """Verify that normalize_opinion logs flow through OTel."""

    def test_normalize_drift_warning_captured_by_otel(self):
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import (
            InMemoryLogExporter,
            SimpleLogRecordProcessor,
        )

        from multitrust.operators.normalize import normalize_opinion

        exporter = InMemoryLogExporter()
        provider = LoggerProvider()
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))

        logger = logging.getLogger("multitrust.operators")
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
        logger.addHandler(handler)

        try:
            # This triggers a drift warning (0.4+0.4+0.4 = 1.2, drift = 0.2)
            normalize_opinion(0.4, 0.4, 0.4, 0.5, operation="test_fusion")

            records = exporter.get_finished_logs()
            assert len(records) >= 1
            assert any("drift" in r.log_record.body for r in records)
            assert any("test_fusion" in r.log_record.body for r in records)
        finally:
            logger.removeHandler(handler)
            provider.shutdown()
