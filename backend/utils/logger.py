"""
logger.py
---------
Centralized logging configuration using Loguru.
Writes to both console and rotating log file.
"""

import sys
import os
from loguru import logger
from backend.config import get_settings

settings = get_settings()

# Remove default handler
logger.remove()

# Console handler — colorized, human-readable
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
)

# File handler — JSON-friendly, rotating
os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
logger.add(
    settings.log_file,
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)

__all__ = ["logger"]
