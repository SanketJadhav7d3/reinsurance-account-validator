from pathlib import Path

from rav.docs import render_rules_md
from rav.rules.loader import load_rules

ROOT = Path(__file__).resolve().parents[1]


def test_committed_rule_catalogue_is_up_to_date():
    """docs/rules.md must equal the output of `rav docs`; run `uv run rav docs` if this fails."""
    committed = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")
    assert committed == render_rules_md(load_rules())


def test_catalogue_lists_every_rule():
    text = render_rules_md(load_rules())
    for n in range(1, 10):
        assert f"## R0{n} - " in text
