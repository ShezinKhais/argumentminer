"""CLI smoke tests.

These invoke the actual Typer commands so that a drift between the documented
command names and the code (for example a command being renamed, or the app
collapsing to a single command) fails a test instead of only surfacing when a
user runs the README example.
"""

import re

from typer.testing import CliRunner

from argumentminer.cli import app

runner = CliRunner()

SAMPLE = (
    "Social media harms teenagers. Studies show depression rose after 2012. "
    "Either we ban it or society collapses."
)


def test_mine_command_runs():
    result = runner.invoke(app, ["mine", SAMPLE])
    assert result.exit_code == 0
    assert "Argument Structure" in result.stdout


def test_mine_reports_fallacy():
    result = runner.invoke(app, ["mine", SAMPLE])
    assert result.exit_code == 0
    assert "Fallac" in result.stdout  # matches the "Detected Fallacies" table


def test_fallacies_command_runs():
    result = runner.invoke(app, ["fallacies", "Either we ban it or society collapses."])
    assert result.exit_code == 0
    assert "False Dichotomy" in result.stdout


def test_fallacies_clean_text():
    result = runner.invoke(app, ["fallacies", "The meeting is scheduled for Tuesday afternoon."])
    assert result.exit_code == 0
    assert "No obvious fallacies" in result.stdout


def test_missing_text_errors():
    result = runner.invoke(app, ["mine"])
    assert result.exit_code == 1


def test_html_report_is_self_contained(tmp_path):
    """The report must open with no network, so a CDN tag is a regression."""
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["mine", SAMPLE, "--html", str(out)])
    assert result.exit_code == 0
    html = out.read_text(encoding="utf-8")
    # The SVG namespace is an identifier the parser needs, not a fetch.
    urls = {u for u in re.findall(r"https?://[^\s\"'<>]+", html)
            if u != "http://www.w3.org/2000/svg"}
    assert urls == set()
    assert "<script src=" not in html
    assert "<link" not in html


def test_html_report_marks_fallacies_on_their_unit(tmp_path):
    """A match belongs on the unit it fired on, not only in the terminal table."""
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["mine", SAMPLE, "--html", str(out)])
    assert result.exit_code == 0
    html = out.read_text(encoding="utf-8")
    assert "False Dichotomy" in html
    assert 'class="matched"' in html      # the matched phrase, marked in place
    assert 'href="#unit-' in html         # the list points back at the unit
