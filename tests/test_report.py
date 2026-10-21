"""Report generation: templates use only known facts; generated documents are complete."""

import re
import string
from pathlib import Path

import pytest

from offhours import report
from offhours.config import REPORTS, ROOT


def test_render_rejects_unknown_fact():
    f = {"a": report.Fact("1", 1.0, "x")}
    assert report.render("value {a}", f) == "value 1"
    with pytest.raises(KeyError):
        report.render("value {b}", f)


@pytest.mark.parametrize("name", ["note", "brief"])
def test_templates_reference_only_known_facts(name):
    tmpl = (report.TEMPLATES / f"{name}.md").read_text(encoding="utf-8")
    report.render(tmpl, report.facts())  # raises on unknown names


@pytest.mark.parametrize("path", ["reports/note/note.md", "reports/note/brief.md",
                                  "reports/headline_figures.md", "README.md"])
def test_generated_documents_have_no_placeholders(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    names = [n for _, n, _, _ in string.Formatter().parse(text.replace("{{", "").replace("}}", ""))
             if n and re.fullmatch(r"[a-z0-9_]+", n)]
    assert not names, f"unfilled placeholders in {path}: {names}"


def test_generated_documents_are_current():
    """The committed note/brief match what the templates render from the committed tables."""
    f = report.facts()
    for name in ("note", "brief"):
        tmpl = (report.TEMPLATES / f"{name}.md").read_text(encoding="utf-8")
        body = (REPORTS / "note" / f"{name}.md").read_text(encoding="utf-8")
        rendered = report.render(tmpl, f)
        # Generated blocks are filled after rendering; compare text before the first block.
        head = rendered.split("<!-- BEGIN GENERATED")[0]
        assert body.startswith(head), f"{name}.md is stale: run --phase report"


def test_p_value_facts_use_comparison_format():
    f = report.facts()
    p_facts = {k: v.text for k, v in f.items() if re.search(r"_p\d?$", k)}
    assert p_facts
    bad = {k: v for k, v in p_facts.items() if not re.fullmatch(r"(= \d\.\d\d|< 0\.0?01)", v)}
    assert not bad, bad


def test_headline_figures_cite_existing_files():
    text = (REPORTS / "headline_figures.md").read_text(encoding="utf-8")
    items = re.findall(r"^## \d+$", text, re.M)
    assert 3 <= len(items) <= 6
    for path in re.findall(r"`(reports/tables/[^`]+)`", text):
        assert (ROOT / path).exists(), path
    for line in re.findall(r"^- Code: `([^`]+)`", text, re.M):
        for p in (x.strip() for x in line.split(",")):
            matches = list(ROOT.glob(p)) if "*" in p else [ROOT / p]
            assert matches and all(Path(m).exists() for m in matches), p
