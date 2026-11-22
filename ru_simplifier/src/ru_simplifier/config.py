# -*- coding: utf-8 -*-
"""Загрузка config.yaml и настройка логирования (консоль + файл).

Детерминизм (INV-4): конфигурация читается один раз и кэшируется;
logging устроено так, чтобы повторные вызовы не дублировали хендлеры.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict

import yaml

PKG_ROOT = Path(__file__).resolve().parents[2]      # .../ru_simplifier (корень проекта)
DEFAULT_CONFIG_PATH = PKG_ROOT / "config.yaml"

_config_cache: Dict[str, Any] | None = None
_lock = threading.Lock()


def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Читает config.yaml (UTF-8). Результат кэшируется — модель/конфиг грузятся один раз."""
    global _config_cache
    with _lock:
        if _config_cache is not None and path is None:
            return _config_cache
        cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        if path is None:
            _config_cache = cfg
        return cfg


def reset_config_cache() -> None:
    """Только для тестов: сбросить кэш конфигурации."""
    global _config_cache
    with _lock:
        _config_cache = None


_LOG_CONFIGURED = False


def setup_logging(cfg: Dict[str, Any] | None = None) -> logging.Logger:
    """Логгер ru_simplifier: консоль + файл; уровень из config.yaml (logging.level).

    Файловый путь разрешается относительно корня пакета, если задан относительным
    (Windows-совместимо через pathlib). Повторные вызовы идемпотентны.
    """
    global _LOG_CONFIGURED
    logger = logging.getLogger("ru_simplifier")
    if _LOG_CONFIGURED:
        return logger

    if cfg is None:
        cfg = load_config()
    log_cfg = cfg.get("logging", {}) or {}
    level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level)
    logger.addHandler(console)

    file_rel = log_cfg.get("file", "logs/ru_simplifier.log")
    file_path = Path(file_rel)
    if not file_path.is_absolute():
        file_path = PKG_ROOT / file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(file_path), encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(fh)

    _LOG_CONFIGURED = True
    logger.debug("Логирование настроено: level=%s file=%s", logging.getLevelName(level), file_path)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Логгер пакета (при первом обращении настраивает handlers)."""
    base = setup_logging()
    return base if not name else logging.getLogger(f"ru_simplifier.{name}")
