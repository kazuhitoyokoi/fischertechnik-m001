import sys
import os
import time
import threading
from pathlib import Path
import pytest
import warnings
from opcua import Client

# pytestのimportモード差異に依存せず、常にプロジェクトルートを解決する
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# テスト対象のモジュールをインポート
import typeM001_opcua

# ==============================================================================
# 製品コード (typeM001_opcua.py) の実際の仕様に合わせた接続先定義
# ==============================================================================
SERVER_URL = "opc.tcp://127.0.0.1:4840/m001"
NS_URI = "urn:local:l1"

# freeopcuaライブラリ内部から出力される大量の非推奨警告を無視してログをスッキリさせる
warnings.filterwarnings("ignore", category=DeprecationWarning, module="opcua")


def get_server_node_by_path(server, ns, folder, name):
    """サーバー側ノードを browse path で取得する。"""
    return server.get_objects_node().get_child([f"{ns}:{folder}", f"{ns}:{name}"])


def get_client_node_by_path(client, ns, folder, name):
    """クライアント側ノードを browse path で取得する。"""
    return client.get_objects_node().get_child([f"{ns}:{folder}", f"{ns}:{name}"])


class ScenarioMockSubprocess:
    """テスト関数ごとに指定されたログの配列を流し込むためのモック"""
    def __init__(self, lines):
        self.lines = lines
        self._index = 0
        self.stdout = self

    def readline(self):
        if self._index < len(self.lines):
            line = self.lines[self._index]
            self._index += 1
            time.sleep(0.01)  # テスト実行を高速にするための微小ウェイト
            return line + "\n"
        return ""

    def poll(self):
        if self._index >= len(self.lines):
            return 0
        return None


@pytest.fixture(scope="function")
def opcua_server():
    """
    テスト関数ごとにクリーンなOPC UAサーバーを起動し、
    製品モジュール側のグローバル変数とサーバー空間のノードを完全に同期させるフィクスチャ
    """
    # 1. 状態キャッシュの初期化
    if hasattr(typeM001_opcua, 'prev_values'):
        typeM001_opcua.prev_values = {}
    
    # 2. サーバーの初期化
    server = typeM001_opcua.init_opcua_server()
    
    # 3. サーバー起動
    server.start()
    time.sleep(0.3)  # ソケットおよび非同期サーバーの立ち上がりを待つ

    # 4. 新しく生成されたサーバーインスタンスから正しいノードを取得し、
    # 製品モジュールのグローバル変数へバインド
    ns = server.get_namespace_index(NS_URI)
    
    typeM001_opcua.ua_photo = get_server_node_by_path(server, ns, "Sensors", "PhotoSensor")
    typeM001_opcua.ua_sw = get_server_node_by_path(server, ns, "Sensors", "PushSwitch")
    typeM001_opcua.ua_magnet = get_server_node_by_path(server, ns, "Sensors", "MagnetSensor")
    typeM001_opcua.ua_led01 = get_server_node_by_path(server, ns, "Actuators", "ProjectorLED")
    typeM001_opcua.ua_motor = get_server_node_by_path(server, ns, "Actuators", "ConveyorMotor")
    typeM001_opcua.ua_led02 = get_server_node_by_path(server, ns, "Actuators", "StatusLED")
    
    yield server
    
    # 5. 後処理（サーバー停止）
    try:
        server.stop()
    except:
        pass
    time.sleep(0.1)


def run_mock_log_flow(lines):
    """モックプロセスを別スレッドで走らせるヘルパー関数"""
    mock_proc = ScenarioMockSubprocess(lines)
    monitor_thread = threading.Thread(
        target=typeM001_opcua.monitor_subprocess, 
        args=(mock_proc,), 
        daemon=True
    )
    monitor_thread.start()
    time.sleep(0.5)  # スレッドがモックログをすべて処理し終えるのを待機


# ==============================================================================
# シナリオ1: 基本的なON/HIGH（正常系）の動作検証
# ==============================================================================
def test_signal_transition_to_true(opcua_server):
    logs = [
        "フォトセンサ: HIGH",
        "非常停止スイッチ: HIGH",
        "磁気センサ: LOW",  # 仕様: LOWで検知(True)
        "モーター: ON",
        "LED01: ON",
        "LED02: HIGH"
    ]
    run_mock_log_flow(logs)

    client = Client(SERVER_URL)
    try:
        client.connect()
        ns = client.get_namespace_index(NS_URI)
        
        assert get_client_node_by_path(client, ns, "Sensors", "PhotoSensor").get_value() is True
        assert get_client_node_by_path(client, ns, "Sensors", "PushSwitch").get_value() is True
        assert get_client_node_by_path(client, ns, "Sensors", "MagnetSensor").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "ConveyorMotor").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "ProjectorLED").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "StatusLED").get_value() is True
    finally:
        client.disconnect()


# ==============================================================================
# シナリオ2: 基本的なOFF/LOW（正常系）の動作検証
# ==============================================================================
def test_signal_transition_to_false(opcua_server):
    logs = [
        "フォトセンサ: HIGH",
        "モーター: ON",
        "フォトセンサ: LOW",
        "モーター: OFF"
    ]
    run_mock_log_flow(logs)

    client = Client(SERVER_URL)
    try:
        client.connect()
        ns = client.get_namespace_index(NS_URI)
        
        assert get_client_node_by_path(client, ns, "Sensors", "PhotoSensor").get_value() is False
        assert get_client_node_by_path(client, ns, "Actuators", "ConveyorMotor").get_value() is False
    finally:
        client.disconnect()


# ==============================================================================
# シナリオ3: 製品コードが持つ「表記揺れキーワード」の網羅検証
# ==============================================================================
def test_alternative_keywords_parsing(opcua_server):
    logs = [
        "フォトセンサ: ワーク検知しました",
        "非常停止が作動中: 警告",
        "磁気センサ: 磁気を検知",
        "モーター: 起動しました",
        "LED01: 点灯",
        "LED02: 点灯"
    ]
    run_mock_log_flow(logs)

    client = Client(SERVER_URL)
    try:
        client.connect()
        ns = client.get_namespace_index(NS_URI)
        
        assert get_client_node_by_path(client, ns, "Sensors", "PhotoSensor").get_value() is True
        assert get_client_node_by_path(client, ns, "Sensors", "PushSwitch").get_value() is True
        assert get_client_node_by_path(client, ns, "Sensors", "MagnetSensor").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "ConveyorMotor").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "ProjectorLED").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "StatusLED").get_value() is True
    finally:
        client.disconnect()


# ==============================================================================
# シナリオ4: 環境ノイズ・無関係なログ行のフィルタリング検証
# ==============================================================================
def test_noise_logs_are_ignored(opcua_server):
    logs = [
        "フォトセンサ: HIGH",
        "--- [SYSTEM INFO] CPU Temperature 45C ---",
        "INFO: unrelated process output line",
        "WARNING: gpiozero test warning"
    ]
    run_mock_log_flow(logs)

    client = Client(SERVER_URL)
    try:
        client.connect()
        ns = client.get_namespace_index(NS_URI)
        
        assert get_client_node_by_path(client, ns, "Sensors", "PhotoSensor").get_value() is True
    finally:
        client.disconnect()


# ==============================================================================
# シナリオ5: 高速な連続状態遷移（トグル動作）への追従性検証
# ==============================================================================
def test_rapid_toggle_state_retention(opcua_server):
    logs = [
        "モーター: ON",
        "モーター: OFF",
        "モーター: ON",
        "モーター: OFF",
        "モーター: ON"
    ]
    run_mock_log_flow(logs)

    client = Client(SERVER_URL)
    try:
        client.connect()
        ns = client.get_namespace_index(NS_URI)
        
        assert get_client_node_by_path(client, ns, "Actuators", "ConveyorMotor").get_value() is True
    finally:
        client.disconnect()


# ==============================================================================
# シナリオ6: 境界値・些細なブレ（大文字小文字・スペース）の判定挙動の検証
# ==============================================================================
def test_string_boundary_and_spaces(opcua_server):
    init_logs = ["フォトセンサ: HIGH", "モーター: ON"]
    run_mock_log_flow(init_logs)

    logs = [
        "フォトセンサ: high",  # 製品コード上、小文字は不一致のため初期値(True)維持
        "モーター: OFF "       # 末尾スペースがあっても in line 判定で一致してFalseへ落とされる
    ]
    run_mock_log_flow(logs)

    client = Client(SERVER_URL)
    try:
        client.connect()
        ns = client.get_namespace_index(NS_URI)
        
        assert get_client_node_by_path(client, ns, "Sensors", "PhotoSensor").get_value() is True
        assert get_client_node_by_path(client, ns, "Actuators", "ConveyorMotor").get_value() is False
    finally:
        client.disconnect()


# ==============================================================================
# シナリオ7: 重複イベントログ出力の抑制検証
# ==============================================================================
def test_duplicate_value_log_suppression(opcua_server, capsys):
    # テスト開始前にこれまでの出力を一度クリア
    capsys.readouterr()

    logs = [
        "モーター: ON",
        "モーター: ON",
        "モーター: ON"
    ]
    run_mock_log_flow(logs)

    captured = capsys.readouterr()
    log_output = captured.out
    
    # ログ出力の変化イベントメッセージをフックする
    assert "ConveyorMotor | 値が" in log_output
    assert log_output.count("変化しました。") == 1


# ==============================================================================
# シナリオ8: 異常系（文字列以外の不正なデータ混入時）の堅牢性検証
# ==============================================================================
def test_invalid_data_type_robustness(opcua_server):
    malicious_inputs = [None, 99999, float('nan')]
    
    for bad_input in malicious_inputs:
        try:
            typeM001_opcua.parse_and_sync(bad_input)
        except Exception as e:
            pytest.fail(f"parse_and_sync が型エラー {type(bad_input)} でクラッシュしました: {e}")