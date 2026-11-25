from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "cedents.yaml"


class CedentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["csv", "xlsx", "json"]
    columns: dict[str, str]  # source header -> canonical column
    date_format: str
    decimal: str
    thousands: str
    true_values: list[str]
    delimiter: str = ","
    header_row: int = 1  # 1-based row holding the column names (xlsx)
    flip_claims: bool = False
    metadata_submitted_on: list[str] | None = None  # path into JSON metadata


def load_cedents(path: Path = DEFAULT_CONFIG) -> dict[str, CedentConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {cid: CedentConfig(**cfg) for cid, cfg in raw["cedents"].items()}
