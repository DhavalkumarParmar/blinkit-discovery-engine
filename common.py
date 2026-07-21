"""Shared helpers: logging (console + rolling data/pipeline.log) and JSONL I/O."""

import json
import logging
import os
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_PATH = os.path.join(DATA_DIR, "pipeline.log")

_FMT = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")


def get_logger(name: str) -> logging.Logger:
    """Logger that writes to console AND data/pipeline.log (rolling, 2MB x 3)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:  # already configured (Streamlit reruns, repeated imports)
        return logger
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(_FMT)
    logger.addHandler(console)
    rolling = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3,
                                  encoding="utf-8")
    rolling.setFormatter(_FMT)
    logger.addHandler(rolling)
    logger.propagate = False
    return logger


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                get_logger("common").warning("Skipping corrupt line %d in %s", line_no, path)
    return items


def append_jsonl(path: str, item: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_jsonl(path: str, items: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
