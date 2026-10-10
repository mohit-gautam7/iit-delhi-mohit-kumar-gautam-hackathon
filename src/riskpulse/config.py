"""Project paths and YAML configuration loading."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
DOCS_DIR = ROOT / "docs"

NEWS_FILE = DATA_DIR / "news_sample.csv"
SOCIAL_FILE = DATA_DIR / "social_sample.csv"
PORTFOLIO_FILE = DATA_DIR / "portfolio.csv"
LABELLED_FILE = DATA_DIR / "labelled_events.csv"


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def scoring_config() -> dict:
    return load_yaml("scoring.yaml")


def scenario_config() -> dict:
    return load_yaml("scenarios.yaml")
