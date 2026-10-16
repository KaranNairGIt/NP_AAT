import asyncio
import threading
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ui.controller import RunController


PAGES = [
    "ui/pages/overview.py",
    "ui/pages/live_network.py",
    "ui/pages/incidents.py",
    "ui/pages/trust.py",
    "ui/pages/security.py",
    "ui/pages/evaluation.py",
    "ui/pages/experiments.py",
    "ui/pages/about.py",
]
APP = Path(__file__).resolve().parents[1] / "app.py"


def test_single_page_switch_works_across_all_pages_while_idle():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    for page in PAGES:
        app.switch_page(page).run()
        assert not app.exception
        assert app.session_state["cids_controller"].run_number == 0


def test_single_page_switch_does_not_restart_an_active_background_run():
    gate = threading.Event()
    controller = RunController()

    async def job(stop_event, feed_sink):
        await asyncio.to_thread(gate.wait)
        return {"seed": 7, "scenario": "all"}

    try:
        assert controller.start("single", job)
        app = AppTest.from_file(APP, default_timeout=30)
        app.session_state["cids_controller"] = controller
        app.run()
        assert controller.status == "Running"
        app.switch_page("ui/pages/trust.py").run()
        assert not app.exception
        assert controller.status == "Running"
        assert controller.run_number == 1
    finally:
        gate.set()
        controller.close()
