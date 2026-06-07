import sys
import importlib
from pathlib import Path

import pytest

# pytestのimportモード差異に依存せず、常にプロジェクトルートを解決する
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def import_app_opcua_module(monkeypatch):
    monkeypatch.setenv("M001_SKIP_STREAMLIT_AUTORUN", "1")
    if "app_opcua" in sys.modules:
        del sys.modules["app_opcua"]
    return importlib.import_module("app_opcua")


class DummyNodeId:
    def to_string(self):
        return "ns=1;s=Dummy"


class DummyNode:
    def __init__(self, value):
        self._value = value
        self.nodeid = DummyNodeId()

    def get_value(self):
        return self._value


class DummyState:
    def __init__(self):
        self.current_idx = -1


def test_streamlit_mock_subprocess_reads_lines(monkeypatch):
    app_opcua = import_app_opcua_module(monkeypatch)
    monkeypatch.setattr(app_opcua.time, "sleep", lambda _: None)

    proc = app_opcua.StreamlitMockSubprocess([" A ", "", "B"])

    assert proc.readline() == "A\n"
    assert proc.readline() == "B\n"
    assert proc.readline() == ""
    assert proc.poll() == 0


def test_get_node_snapshot_success(monkeypatch):
    app_opcua = import_app_opcua_module(monkeypatch)

    monkeypatch.setattr(app_opcua, "get_node_by_path", lambda *_: DummyNode(True))
    value, node_id = app_opcua.get_node_snapshot(object(), 1, "Sensors", "PhotoSensor")

    assert value is True
    assert node_id == "ns=1;s=Dummy"


def test_get_node_snapshot_error(monkeypatch):
    app_opcua = import_app_opcua_module(monkeypatch)

    def raise_error(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_opcua, "get_node_by_path", raise_error)
    value, node_id = app_opcua.get_node_snapshot(object(), 1, "Sensors", "PhotoSensor")

    assert value == "取得エラー"
    assert node_id == "Unknown"


def test_run_scenario_loop_updates_index_and_calls_monitor(monkeypatch):
    app_opcua = import_app_opcua_module(monkeypatch)
    monkeypatch.setattr(app_opcua.time, "sleep", lambda *_: None)
    monkeypatch.setattr(app_opcua, "SCENARIOS", [{"title": "one", "logs": ["x"], "duration": 0}])

    calls = {"count": 0}

    def monitor_once(_):
        calls["count"] += 1
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(app_opcua.typeM001_opcua, "monitor_subprocess", monitor_once)
    state = DummyState()

    with pytest.raises(RuntimeError, match="stop-loop"):
        app_opcua.run_scenario_loop(state)

    assert state.current_idx == 0
    assert calls["count"] == 1
