"""
Logging configuration for QMS.

Provides consistent log formatting across all modules.
"""

import logging
import sys
from typing import Dict

_loggers: Dict[str, logging.Logger] = {}


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger for a module.

    Args:
        name: Logger name (e.g., 'qms.welding', 'qms.workforce')
        level: Logging level (default: INFO)

    Returns:
        Configured logger
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _loggers[name] = logger
    return logger
