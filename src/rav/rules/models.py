"""Rule-config schema. A bad rule file fails loudly on load."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True)
class Finding:
    """One rule firing on one account line (the engine adds rule id and severity)."""

    line_ref: str
    message: str


class RuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^R\d{2}$")
    name: str
    detects: str = Field(pattern=r"^D\d{2}$")  # which planted defect type this rule targets
    severity: Literal["error", "warning"]
    description: str
    type: Literal["sql", "python"]
    sql_file: str | None = None
    function: str | None = None
    params: dict[str, Decimal] = {}
    enabled: bool = True

    @model_validator(mode="after")
    def _target_matches_type(self) -> "RuleConfig":
        if self.type == "sql" and not self.sql_file:
            raise ValueError("type 'sql' requires sql_file")
        if self.type == "python" and not self.function:
            raise ValueError("type 'python' requires function")
        return self
