from pathlib import Path

import yaml
from pydantic import ValidationError

from rav.rules.models import RuleConfig

ROOT = Path(__file__).resolve().parents[3]
RULES_DIR = ROOT / "config" / "rules"


def load_rules(directory: Path = RULES_DIR, root: Path = ROOT) -> list[RuleConfig]:
    rules = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            rule = RuleConfig(**yaml.safe_load(path.read_text(encoding="utf-8")))
        except (ValidationError, TypeError) as exc:
            raise ValueError(f"invalid rule file {path.name}: {exc}") from exc
        if rule.sql_file and not (root / rule.sql_file).is_file():
            raise ValueError(f"{path.name}: sql_file {rule.sql_file} does not exist")
        rules.append(rule)
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ids")
    return sorted(rules, key=lambda r: r.id)
