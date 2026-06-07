import os

# gpiozeroにモックを使用することを指示
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

import streamlit as st
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPin

# ==== PWMエラー回避パッチ ====
def mock_set_frequency(self, value):
    pass
MockPin._set_frequency = mock_set_frequency

SCENARIO_PRESETS = {
    "シナリオ01: 正常運転": {"toggle_photo": True, "toggle_sw": False, "toggle_magnet": False},
    "シナリオ02: 磁気検知": {"toggle_photo": True, "toggle_sw": False, "toggle_magnet": True},
    "シナリオ03: 非常停止": {"toggle_photo": True, "toggle_sw": True, "toggle_magnet": False},
    "シナリオ04: 起動直後": {"toggle_photo": False, "toggle_sw": False, "toggle_magnet": False},
}


def apply_scenario(state):
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()


def drive_mock_inputs(main_module):
    if st.session_state['toggle_photo']:
        main_module.photo.pin.drive_high()  # current_photo = 1 (ワーク検知)
    else:
        main_module.photo.pin.drive_low()   # current_photo = 0 (ワークなし)

    if st.session_state['toggle_sw']:
        main_module.sw.pin.drive_high()     # current_sw = 1 (!!非常停止中!!)
    else:
        main_module.sw.pin.drive_low()      # current_sw = 0 (解除/正常)

    # 見た目ON/OFFをロジック（HIGH/LOW）と逆にドライブ
    if st.session_state['toggle_magnet']:
        main_module.magnet.pin.drive_low()   # current_magnet = 0 (磁気検知)
    else:
        main_module.magnet.pin.drive_high()  # current_magnet = 1 (磁気なし)


def render_output_status(title, caption, is_active):
    st.subheader(title)
    st.caption(caption)
    if is_active:
        st.success("点灯中 (HIGH)" if "LED" in title else "回転中 (HIGH)")
    else:
        st.error("消灯 (LOW)" if "LED" in title else "停止 (LOW)")

def initialize_session_state():
    if 'initialized' in st.session_state:
        return

    Device.pin_factory = MockFactory()
    st.session_state['toggle_photo'] = False
    st.session_state['toggle_sw'] = False
    st.session_state['toggle_magnet'] = False
    st.session_state['initialized'] = True


def render_app():
    # メインモジュールのインポート（これだけで無限ループは起動しなくなります）
    import typeM001_gpiozero as main

    st.set_page_config(page_title="システム シミュレータ", layout="wide")
    initialize_session_state()

    st.title("M001 シミュレータ")
    st.write("物理配線モデル(LED、モーター、各種センサー)を画面上に再現します。")
    st.markdown("---")

    # --- サイドバー：シナリオテスト実行パネル ---
    st.sidebar.header("シナリオテスト実行")
    st.sidebar.write("各ボタンを押すと、pytestのシナリオと同等の入力を再現します。")

    for scenario_name, scenario_state in SCENARIO_PRESETS.items():
        if st.sidebar.button(scenario_name):
            apply_scenario(scenario_state)

    st.markdown("---")

    # --- 入力側のUI ---
    st.header("センサー / スイッチ入力 (Pin 5, 6, 16)")
    st.caption("※トグル操作によって mock ピンへの電圧が直接切り替わります。")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.toggle("フォトセンサ (Pin 5) \n[ON = ワーク検知(HIGH)]", key="toggle_photo")

    with col2:
        st.toggle("非常停止SW (Pin 16) \n[ON = 非常停止(HIGH)]", key="toggle_sw")

    with col3:
        st.toggle("磁気センサ (Pin 6) \n[ON = 磁気検知]", key="toggle_magnet")

    # 画面のトグル状態を実際のMockピンの状態へ反映
    drive_mock_inputs(main)

    # メインロジックを1ステップ実行して、アクチュエータの状態を更新
    main.control_logic()

    st.markdown("---")

    # --- 出力側のUI ---
    st.header("アクチュエータ / LED出力 (Pin 22, 23, 25)")
    out_col1, out_col2, out_col3 = st.columns(3)

    with out_col1:
        render_output_status("LED 01 (Pin 23)", "フォトセンサ用投光器", main.led01.is_active)

    with out_col2:
        render_output_status("モーター (Pin 22)", "コンベア等の駆動", main.motor.is_active)

    with out_col3:
        render_output_status("LED 02 (Pin 25)", "ステータスランプ", main.led02.is_active)


if os.environ.get("M001_SKIP_STREAMLIT_AUTORUN") != "1":
    render_app()