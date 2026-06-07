import sys
import importlib
from pathlib import Path

# pytestのimportモード差異に依存せず、常にプロジェクトルートを解決する
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def import_app_module(monkeypatch):
    monkeypatch.setenv("M001_SKIP_STREAMLIT_AUTORUN", "1")
    if "app" in sys.modules:
        del sys.modules["app"]
    return importlib.import_module("app")


class FakePin:
    def __init__(self):
        self.calls = []

    def drive_high(self):
        self.calls.append("high")

    def drive_low(self):
        self.calls.append("low")


class FakeInput:
    def __init__(self):
        self.pin = FakePin()


class FakeMainModule:
    def __init__(self):
        self.photo = FakeInput()
        self.sw = FakeInput()
        self.magnet = FakeInput()


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.rerun_called = False
        self.success_messages = []
        self.error_messages = []

    def rerun(self):
        self.rerun_called = True

    def subheader(self, _):
        pass

    def caption(self, _):
        pass

    def success(self, message):
        self.success_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)


def test_apply_scenario_updates_session_and_reruns(monkeypatch):
    app = import_app_module(monkeypatch)
    fake_st = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_st)

    app.apply_scenario({"toggle_photo": True, "toggle_sw": False, "toggle_magnet": True})

    assert fake_st.session_state["toggle_photo"] is True
    assert fake_st.session_state["toggle_sw"] is False
    assert fake_st.session_state["toggle_magnet"] is True
    assert fake_st.rerun_called is True


def test_drive_mock_inputs_maps_toggles_to_pins(monkeypatch):
    app = import_app_module(monkeypatch)
    fake_st = FakeStreamlit()
    fake_st.session_state = {
        "toggle_photo": True,
        "toggle_sw": False,
        "toggle_magnet": True,
    }
    monkeypatch.setattr(app, "st", fake_st)

    fake_main = FakeMainModule()
    app.drive_mock_inputs(fake_main)

    assert fake_main.photo.pin.calls == ["high"]
    assert fake_main.sw.pin.calls == ["low"]
    # 磁気トグルは見た目ONでdrive_low
    assert fake_main.magnet.pin.calls == ["low"]


def test_render_output_status_led_and_motor(monkeypatch):
    app = import_app_module(monkeypatch)
    fake_st = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_st)

    app.render_output_status("LED 01 (Pin 23)", "dummy", True)
    app.render_output_status("モーター (Pin 22)", "dummy", False)

    assert "点灯中 (HIGH)" in fake_st.success_messages
    assert "停止 (LOW)" in fake_st.error_messages
