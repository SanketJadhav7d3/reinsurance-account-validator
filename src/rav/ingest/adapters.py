"""One adapter per source format. Each returns a DataFrame with canonical column names
and raw (un-normalised) values; parsing of numbers and dates happens in normalise.py."""

import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from rav.ingest.config import CedentConfig


def _canonical(df: pd.DataFrame, cfg: CedentConfig) -> pd.DataFrame:
    return df.rename(columns=cfg.columns)


def read_csv(path: Path, cfg: CedentConfig) -> pd.DataFrame:
    df = pd.read_csv(path, sep=cfg.delimiter, dtype=str, keep_default_na=False, encoding="utf-8")
    return _canonical(df, cfg)


def read_xlsx(path: Path, cfg: CedentConfig) -> pd.DataFrame:
    """Skip the title and merged group-header rows; header names come from header_row."""
    ws = load_workbook(path, data_only=True).active
    rows = list(ws.iter_rows(min_row=cfg.header_row, values_only=True))
    df = pd.DataFrame(rows[1:], columns=list(rows[0]), dtype=object)
    df = df.dropna(how="all")
    return _canonical(df, cfg)


def read_json(path: Path, cfg: CedentConfig) -> pd.DataFrame:
    doc = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(doc["lines"], dtype=object)
    if cfg.metadata_submitted_on:
        value = doc
        for key in cfg.metadata_submitted_on:
            value = value[key]
        df["submitted_on"] = value
    return _canonical(df, cfg)


ADAPTERS = {"csv": read_csv, "xlsx": read_xlsx, "json": read_json}
