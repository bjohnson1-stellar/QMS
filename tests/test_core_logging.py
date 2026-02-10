"""Tests for logging configuration."""

import logging

from qms.core.logging import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)


def test_get_logger_cached():
    logger1 = get_logger("test.cached")
    logger2 = get_logger("test.cached")
    assert logger1 is logger2


def test_get_logger_has_handler():
    logger = get_logger("test.handler")
    assert len(logger.handlers) >= 1


def test_get_logger_format_includes_name():
    logger = get_logger("test.format")
    fmt = logger.handlers[0].formatter._fmt
    assert "%(name)s" in fmt
