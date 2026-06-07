import sys
import os
import logging
import subprocess
import threading
import time
from opcua import Server, ua

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 接続/名前空間定義
SERVER_ENDPOINT = "opc.tcp://0.0.0.0:4840/m001"
NAMESPACE_URI = "urn:local:l1"
NAMESPACE_ARRAY = ["http://opcfoundation.org/UA/", NAMESPACE_URI, "urn:local:l2"]

# 使用する名前空間のインデックスを 1 に設定
NS_INDEX = 1

# OPC UA サーバー用のグローバルノード変数
ua_photo = None
ua_sw = None
ua_magnet = None
ua_led01 = None
ua_motor = None
ua_led02 = None

# 値の変化を監視するための前回値保持辞書
prev_values = {}


def _node_id(path):
    return f"ns={NS_INDEX};s={path}"


NODE_IDS = {
    "photo": _node_id("Sensors.PhotoSensor"),
    "sw": _node_id("Sensors.PushSwitch"),
    "magnet": _node_id("Sensors.MagnetSensor"),
    "led01": _node_id("Actuators.ProjectorLED"),
    "motor": _node_id("Actuators.ConveyorMotor"),
    "led02": _node_id("Actuators.StatusLED"),
}


def _get_child_node(server, ns, folder, name):
    return server.get_objects_node().get_child([f"{ns}:{folder}", f"{ns}:{name}"])


def bind_server_nodes(server, ns=NS_INDEX):
    """既存のアドレス空間からグローバルノード参照を再バインドする。"""
    global ua_photo, ua_sw, ua_magnet, ua_led01, ua_motor, ua_led02

    ua_photo = _get_child_node(server, ns, "Sensors", "PhotoSensor")
    ua_sw = _get_child_node(server, ns, "Sensors", "PushSwitch")
    ua_magnet = _get_child_node(server, ns, "Sensors", "MagnetSensor")
    ua_led01 = _get_child_node(server, ns, "Actuators", "ProjectorLED")
    ua_motor = _get_child_node(server, ns, "Actuators", "ConveyorMotor")
    ua_led02 = _get_child_node(server, ns, "Actuators", "StatusLED")


def init_opcua_server():
    """OPC UA サーバーの初期化、エンドポイント設定、アドレス空間の構築"""
    global ua_photo, ua_sw, ua_magnet, ua_led01, ua_motor, ua_led02
    server = Server()
    
    # エンドポイントのパスを /m001 に設定
    server.set_endpoint(SERVER_ENDPOINT)
    
    # 名前空間の固定
    ns_node = server.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
    ns_node.set_value(NAMESPACE_ARRAY)
    
    logger.info("OPC UA サーバ名前空間の登録（インデックス %d を使用します）", NS_INDEX)

    objects = server.get_objects_node()
    
    # 指定したインデックス（NS_INDEX = 1）でフォルダを作成
    sensors_folder = objects.add_folder(NS_INDEX, "Sensors")
    actuators_folder = objects.add_folder(NS_INDEX, "Actuators")

    # 指定したインデックス（NS_INDEX = 1）で各ノード変数を登録
    ua_photo = sensors_folder.add_variable(NS_INDEX, "PhotoSensor", False)
    ua_sw = sensors_folder.add_variable(NS_INDEX, "PushSwitch", False)
    ua_magnet = sensors_folder.add_variable(NS_INDEX, "MagnetSensor", False)

    ua_led01 = actuators_folder.add_variable(NS_INDEX, "ProjectorLED", False)
    ua_motor = actuators_folder.add_variable(NS_INDEX, "ConveyorMotor", False)
    ua_led02 = actuators_folder.add_variable(NS_INDEX, "StatusLED", False)

    # クライアント側からの書き込み属性許可
    ua_photo.set_writable()
    ua_sw.set_writable()
    ua_magnet.set_writable()

    return server


def set_node_value_with_log(node, node_id_str, value):
    """
    ノードの値が変化した時のみ、ノードIDと詳細情報をログに出力して値を更新する
    """
    global prev_values
    if node is None:
        return

    old_value = prev_values.get(node_id_str)
    
    if old_value != value:
        node.set_value(value)
        prev_values[node_id_str] = value
        # ノードID、変化前の値、変化後の詳細情報をログ出力
        print(f"[OPC UAデータ変化イベント] NodeID: {node_id_str} | 値が {old_value} から {value} に変化しました。")


def _sync_from_line_markers(line, node, node_id_str, true_markers, false_markers):
    if any(marker in line for marker in true_markers):
        set_node_value_with_log(node, node_id_str, True)
    elif any(marker in line for marker in false_markers):
        set_node_value_with_log(node, node_id_str, False)


def parse_and_sync(line):
    """
    typeM001_gpiozero.py の標準出力を解析し、対応する OPC UA ノードの値を更新する。
    """
    global ua_photo, ua_sw, ua_magnet, ua_led01, ua_motor, ua_led02

    try:
        if not isinstance(line, str):
            return

        rules = [
            (("フォトセンサ",), ua_photo, NODE_IDS["photo"], ("HIGH", "ワーク検知"), ("LOW", "ワークなし")),
            (("非常停止スイッチ", "非常停止が作動中"), ua_sw, NODE_IDS["sw"], ("HIGH", "作動中"), ("LOW", "解除")),
            (("磁気センサ", "磁気を検知"), ua_magnet, NODE_IDS["magnet"], ("LOW", "検知"), ("HIGH", "磁気なし")),
            (("モーター",), ua_motor, NODE_IDS["motor"], ("起動", "ON"), ("停止", "OFF")),
            (("LED02",), ua_led02, NODE_IDS["led02"], ("HIGH", "点灯"), ("LOW", "消灯")),
            (("LED01",), ua_led01, NODE_IDS["led01"], ("ON", "点灯"), ("OFF", "消灯")),
        ]

        for triggers, node, node_id_str, true_markers, false_markers in rules:
            if any(trigger in line for trigger in triggers):
                _sync_from_line_markers(line, node, node_id_str, true_markers, false_markers)
                break

    except Exception as e:
        logger.error("ライン解析またはOPC UA同期中にエラーが発生しました: %s", e)


def monitor_subprocess(proc):
    """子プロセスの標準出力をリアルタイムで行単位で読み取るスレッド"""
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            # 元スクリプトの出力をそのまま画面に表示
            sys.stdout.write(line)
            sys.stdout.flush()
            # 出力内容に基づいて OPC UA ノードを更新
            parse_and_sync(line.strip())


def main():
    # 1. OPC UA サーバーの初期化
    server = init_opcua_server()
    logger.info("OPC UA サーバを起動します。")
    server.start()
    logger.info("OPC UA サーバが正常に起動しました (Endpoint: %s)", SERVER_ENDPOINT)

    # 2. 既存の typeM001_gpiozero.py を子プロセスとして起動
    target_script = os.path.join(os.path.dirname(__file__), "typeM001_gpiozero.py")
    if not os.path.exists(target_script):
        logger.error("エラー: typeM001_gpiozero.py が見つかりません。")
        server.stop()
        sys.exit(1)

    logger.info("typeM001_gpiozero.py を子プロセスとして起動します。")
    
    proc = subprocess.Popen(
        [sys.executable, "-u", target_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # 3. 子プロセスの出力を監視する非同期スレッドを開始
    monitor_thread = threading.Thread(target=monitor_subprocess, args=(proc,), daemon=True)
    monitor_thread.start()

    print(f"== OPC UA SERVER RUNNING (ns={NS_INDEX} モード) ==")
    print("CTRL+C = END")

    try:
        while proc.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n== 終了シグナルを受信しました ==")
    finally:
        if proc.poll() is None:
            logger.info("typeM001_gpiozero.py プロセスを終了します。")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        logger.info("OPC UA サーバを停止します。")
        server.stop()


if __name__ == "__main__":
    main()