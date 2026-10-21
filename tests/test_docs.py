"""Disclosure tests: open gaps and not-reproducible targets must be in README and the note."""

import re

from offhours import reconciliation as rc
from offhours.docs import NOTE, README


def _limitations(text: str) -> str:
    """Body of the note's Limitations section (from its heading to the next '## ' heading)."""
    m = re.search(r"^## [0-9. ]*Limitations\s*$(.*?)(?=^## )", text, re.S | re.M)
    assert m, "note has no '## Limitations' section"
    return m.group(1)


def test_open_gaps_disclosed_in_readme_and_note_limitations():
    listed = rc.listed_targets()
    readme = README.read_text(encoding="utf-8")
    limits = _limitations(NOTE.read_text(encoding="utf-8"))
    missing = [f"{t} ({kind}) missing from {where}"
               for t, kind in listed.items()
               for where, text in (("README.md", readme), ("note Limitations", limits))
               if f"`{t}`" not in text]
    assert not missing, "; ".join(missing)


def test_tier_coverage_stated_in_readme_and_note_data_section():
    readme = README.read_text(encoding="utf-8")
    note = NOTE.read_text(encoding="utf-8")
    data = re.search(r"^## [0-9. ]*Data\s*$(.*?)(?=^## )", note, re.S | re.M).group(1)
    for where, text in (("README.md", readme), ("note Data", data)):
        assert "Tier 1" in text and "Tier 2" in text, f"tier coverage not stated in {where}"
        assert "BEGIN GENERATED:coverage" in text, f"coverage table block missing in {where}"
