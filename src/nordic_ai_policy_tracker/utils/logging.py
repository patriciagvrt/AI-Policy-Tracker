"""Shared logging setup.

Every script in scripts/ calls get_logger(__name__) at the top so log
messages are tagged with the module that produced them and always go to
both the console and a per-run file under logs/. Errors are logged with
enough detail to debug, but this function never logs secrets (there are
none in this pilot -- collection is of public pages only -- but the pattern
is here so it's not forgotten if an API key is added later).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def get_logger(
    name: str, logs_dir: str | Path = "logs", level: int = logging.INFO
) -> logging.Logger:
    """Return a configured logger that writes to console and logs/<name>.log.

    Safe to call repeatedly (e.g. once per module) -- handlers are only
    attached the first time a given logger name is configured.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    try:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        safe_name = name.replace(".", "_")
        file_handler = logging.FileHandler(logs_path / f"{safe_name}.log", encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        # If the filesystem is read-only or logs/ can't be created, fall
        # back to console-only logging rather than crashing the pipeline.
        logger.warning("Could not create log file handler; logging to console only.")

    return logger
