"""Headless smoke test of the Streamlit app (default page) using Streamlit's AppTest."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_dashboard_overview_renders_without_exceptions():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert any("Executive Risk Overview" in t.value for t in at.title)
