"""
Structured Logging Framework.

Cung cấp:
- Structured JSON logging cho production
- Pretty console logging cho development
- Per-module loggers
- Performance timing decorator
- Context-aware logging (request_id, video_id, etc.)
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
import time
import functools
from pathlib import Path
from typing import Any, Callable, Optional
from datetime import datetime, timezone


# ──────────────────────────────────────────────
#  Custom Formatter
# ──────────────────────────────────────────────

class PrettyFormatter(logging.Formatter):
    """Console formatter với màu sắc và emoji."""

    LEVEL_ICONS = {
        "DEBUG":    "🔍",
        "INFO":     "ℹ️ ",
        "WARNING":  "⚠️ ",
        "ERROR":    "❌",
        "CRITICAL": "🔥",
    }

    LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        icon = self.LEVEL_ICONS.get(record.levelname, "")
        color = self.LEVEL_COLORS.get(record.levelname, "")
        reset = self.RESET

        # Timestamp
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]

        # Module name (shortened)
        module = record.name
        if module.startswith("src."):
            module = module[4:]

        # Extra context
        extras = ""
        for key in ("video_id", "channel", "phase", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                extras += f" {key}={val}"

        msg = f"{color}{icon} {ts} [{record.levelname:<7}] {module}: {record.getMessage()}{extras}{reset}"

        if record.exc_info and record.exc_info[0] is not None:
            msg += "\n" + self.formatException(record.exc_info)

        return msg


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter cho file logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "line": record.lineno,
            "file": record.filename,
        }

        # Extra context fields
        for key in ("video_id", "channel", "phase", "duration_ms",
                     "clip_count", "error_type"):
            val = getattr(record, key, None)
            if val is not None:
                log_data[key] = val

        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


# ──────────────────────────────────────────────
#  Logger Setup
# ──────────────────────────────────────────────

_initialized = False


def setup_logging(
    level: str = "INFO",
    log_dir: str = "./logs",
    log_file: str = "reupbanconten.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Initialize logging framework.
    Call once at application startup.
    """
    global _initialized
    if _initialized:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger("src")
    root_logger.setLevel(log_level)

    # Prevent duplicate handlers
    root_logger.handlers.clear()

    # 1. Console handler (pretty)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(PrettyFormatter())
    root_logger.addHandler(console_handler)

    # 2. File handler (JSON, rotating)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # File gets everything
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    _initialized = True

    root_logger.info(
        "Logging initialized",
        extra={"phase": "startup"},
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing video", extra={"video_id": "abc123"})
    """
    return logging.getLogger(name)


# ──────────────────────────────────────────────
#  Timing Decorator
# ──────────────────────────────────────────────

def log_duration(
    logger: Optional[logging.Logger] = None,
    level: int = logging.INFO,
    msg_template: str = "{func_name} completed",
) -> Callable:
    """
    Decorator đo thời gian thực thi và log.

    Usage:
        @log_duration()
        def process_video(path):
            ...

        @log_duration(logger=my_logger, msg_template="Downloaded {func_name}")
        async def download(url):
            ...
    """
    def decorator(func: Callable) -> Callable:
        _logger = logger or get_logger(func.__module__)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                _logger.log(
                    level,
                    msg_template.format(func_name=func.__name__),
                    extra={"duration_ms": elapsed_ms},
                )
                return result
            except Exception:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                _logger.error(
                    f"{func.__name__} failed after {elapsed_ms}ms",
                    exc_info=True,
                    extra={"duration_ms": elapsed_ms},
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                _logger.log(
                    level,
                    msg_template.format(func_name=func.__name__),
                    extra={"duration_ms": elapsed_ms},
                )
                return result
            except Exception:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                _logger.error(
                    f"{func.__name__} failed after {elapsed_ms}ms",
                    exc_info=True,
                    extra={"duration_ms": elapsed_ms},
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
