import streamlit as st
import time
import threading
import os
import warnings
from opcua import Client

# gpiozeroのモックモードを強制有効化（実機なしで動作させるため）
if 'GPIOZERO_PIN_FACTORY' not in os.environ:
    os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

# テスト対象のモジュールをインポート
import typeM001_opcua

# freeopcuaライブラリの非推奨警告を非表示にする
warnings.filterwarnings("ignore", category=DeprecationWarning, module="opcua")

# ==============================================================================
# 設定定義 (typeM001_opcua.py の仕様に完全準拠)
# ==============================================================================
SERVER_URL = typeM001_opcua.SERVER_ENDPOINT.replace("0.0.0.0", "127.0.0.1")
NS_URI = typeM001_opcua.NAMESPACE_URI
REFRESH_INTERVAL_SEC = 0.5

# 監視ノードの定義 (Folder, Name, ラベル名)
NODE_CONFIGS = [
    ("Sensors", "PhotoSensor", "📸 フォトセンサ (PhotoSensor)"),
    ("Sensors", "PushSwitch", "🚨 非常停止/プッシュスイッチ (PushSwitch)"),
    ("Sensors", "MagnetSensor", "🧲 磁気センサ (MagnetSensor)"),
    ("Actuators", "ProjectorLED", "💡 投光器LED (ProjectorLED)"),
    ("Actuators", "ConveyorMotor", "⚙️ コンベアモーター (ConveyorMotor)"),
    ("Actuators", "StatusLED", "🟢 ステータスLED (StatusLED)"),
]

# ==============================================================================
# 自動テストシナリオの定義
# ==============================================================================
SCENARIOS = [
    {
        "title": "🟢 シナリオ1: 全初期化 (すべてOFF/LOW)",
        "logs": ["フォトセンサ: LOW", "非常停止スイッチ: LOW", "磁気センサ: HIGH", "モーター: OFF", "LED01: 消灯", "LED02: LOW"],
        "duration": 4
    },
    {
        "title": "📸 シナリオ2: ワーク（製品）の接近検知",
        "logs": ["フォトセンサ: ワーク検知しました", "LED01: ON"],
        "duration": 5
    },
    {
        "title": "⚙️ シナリオ3: 製造ラインのコンベア起動",
        "logs": ["モーター: 起動しました", "LED02: 点灯"],
        "duration": 5
    },
    {
        "title": "🧲 シナリオ4: パレットの磁気マーカー通過",
        "logs": ["磁気センサ: 磁気を検知"],
        "duration": 4
    },
    {
        "title": "🚨 シナリオ5: 緊急停止ボタンの押下（エラー状態発生）",
        "logs": ["非常停止スイッチ: HIGH", "非常停止が作動中: 警告", "モーター: OFF"],
        "duration": 6
    },
    {
        "title": "🔄 シナリオ6: 復旧・ライン再稼働",
        "logs": ["非常停止スイッチ: LOW", "フォトセンサ: LOW", "磁気センサ: HIGH", "モーター: ON"],
        "duration": 5
    }
]

# スレッド間で現在進行中のインデックスを安全に共有するためのデータ箱
class ScenarioState:
    def __init__(self):
        self.current_idx = 0

# ==============================================================================
# バックグラウンドでのログ注入とシナリオ制御
# ==============================================================================
class StreamlitMockSubprocess:
    """ログを1行ずつパイプラインに流し込むモック"""
    def __init__(self, lines):
        self.lines = [line.strip() for line in lines if line.strip()]
        self._index = 0
        self.stdout = self

    def readline(self):
        if self._index < len(self.lines):
            line = self.lines[self._index]
            self._index += 1
            time.sleep(0.05)
            return line + "\n"
        return ""

    def poll(self):
        if self._index >= len(self.lines):
            return 0
        return None

def run_scenario_loop(state_obj):
    """バックグラウンドで全シナリオを無限ループ実行する関数"""
    while True:
        for idx, sc in enumerate(SCENARIOS):
            # 現在のシナリオのインデックスを保存
            state_obj.current_idx = idx
            
            # ログを製品モジュールの同期機構へ流し込む
            mock_proc = StreamlitMockSubprocess(sc["logs"])
            typeM001_opcua.monitor_subprocess(mock_proc)
            
            # 指定された秒数だけ現在の状態をキープ
            time.sleep(sc["duration"])

def get_node_by_path(client, ns, folder, name):
    """Browse Path を使用してクライアントから安全にノードを取得する"""
    return client.get_objects_node().get_child([f"{ns}:{folder}", f"{ns}:{name}"])


def get_node_snapshot(client, ns, folder, name):
    try:
        node = get_node_by_path(client, ns, folder, name)
        return node.get_value(), node.nodeid.to_string()
    except Exception:
        return "取得エラー", "Unknown"

# ==============================================================================
# バックグラウンドサーバーおよびシナリオスレッドの初期化（初回のみ）
# ==============================================================================
@st.cache_resource
def init_backend(_state_obj):
    """OPC UAサーバーの起動とグローバルバインド、シナリオループの開始"""
    if hasattr(typeM001_opcua, 'prev_values'):
        typeM001_opcua.prev_values = {}
        
    server = typeM001_opcua.init_opcua_server()
    server.start()
    time.sleep(0.5)

    ns = server.get_namespace_index(NS_URI)
    typeM001_opcua.bind_server_nodes(server, ns)
    
    # シナリオ実行用のバックグラウンドスレッドを開始（データオブジェクトを渡す）
    t = threading.Thread(target=run_scenario_loop, args=(_state_obj,), daemon=True)
    t.start()
    
    return server

# サーバーと自動シナリオの稼働
def render_app():
    st.set_page_config(page_title="fischertechnik 自動シミュレータ", layout="wide")

    if 'state_box' not in st.session_state:
        st.session_state['state_box'] = ScenarioState()
    state_box = st.session_state['state_box']

    # サーバーと自動シナリオの稼働
    server_instance = init_backend(state_box)

    # ==============================================================================
    # Streamlit UI 画面の構築
    # ==============================================================================
    st.title("🏭 fischertechnik-m001 自動シナリオ・シミュレータ")
    st.caption("実機なしで、定義された実稼働テストシナリオを自動で連続実行し、OPC UAノードの変化をリアルタイム追跡します。")

    # 画面分割 (左: 全体シナリオ工程一覧、右: OPC UAノードのリアルタイムステータス)
    col_left, col_right = st.columns([4, 5])

    with col_left:
        st.subheader("📂 全体シナリオ工程一覧 (自動ループ中)")

        # スレッド側で更新された最新の進行インデックスを取得
        current_idx = state_box.current_idx

        # 各工程のリスト表示
        for i, sc in enumerate(SCENARIOS):
            if i == current_idx:
                # 現在アクティブな工程をハイライト
                st.markdown(f"👉 **{sc['title']}** *(実行中)*")
            else:
                st.markdown(f"⚪ {sc['title']}")

        st.markdown("---")
        # プロセスを確実に落とす安全停止ボタン
        if st.button("🛑 シミュレータを安全に停止", type="secondary", use_container_width=True):
            st.warning("⚠️ OPC UAサーバーをシャットダウンし、プロセスを終了しています。このタブを閉じてください。")
            try:
                server_instance.stop()
            except Exception:
                pass
            os._exit(0)

    with col_right:
        st.subheader("📊 OPC UA リアルタイム・アドレス空間")
        st.write(f"🔌 `{SERVER_URL}` | Namespace URI: `{NS_URI}`")
        st.write(f"⏱️ 最終同期時刻: {time.strftime('%H:%M:%S')}")

        # クライアントから現在のリアルタイムなノード値を取得してマッピング
        try:
            with Client(SERVER_URL) as client:
                ns = client.get_namespace_index(NS_URI)

                st.markdown("### 🔹 センサー群 (Sensors)")
                sens_cols = st.columns(3)

                st.markdown("### 🔸 アクチュエータ群 (Actuators)")
                act_cols = st.columns(3)

                for idx_cfg, (folder, name, label) in enumerate(NODE_CONFIGS):
                    current_value, node_id_str = get_node_snapshot(client, ns, folder, name)

                    # 状態インジケータ文字列の作成
                    if current_value is True:
                        state_text = "🟢 TRUE (ON / HIGH)"
                    elif current_value is False:
                        state_text = "🔴 FALSE (OFF / LOW)"
                    else:
                        state_text = f"❓ {current_value}"

                    # 適切なカラムを選択して出力
                    target_cols = sens_cols if folder == "Sensors" else act_cols
                    col_target = target_cols[idx_cfg % 3]

                    with col_target:
                        st.metric(label=label, value="TRUE" if current_value is True else "FALSE")
                        st.write(state_text)
                        st.caption(f"`{node_id_str}`")
                        st.markdown("---")

        except Exception as e:
            st.error(f"❌ OPC UA サーバーへの接続失敗: {e}")

    # 500ms（0.5秒）待機して画面を自動再描画（リフレッシュループ）
    time.sleep(REFRESH_INTERVAL_SEC)
    st.rerun()


if os.environ.get("M001_SKIP_STREAMLIT_AUTORUN") != "1":
    render_app()