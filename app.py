import os
import sys

# gpiozeroにモックを使用することを指示
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

import streamlit as st
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPin

# ==== PWMエラー回避パッチ ====
def mock_set_frequency(self, value):
    pass
MockPin._set_frequency = mock_set_frequency

st.set_page_config(page_title="システム シミュレータ", layout="wide")

# --- 初期化処理 ---
if 'initialized' not in st.session_state:
    Device.pin_factory = MockFactory()
    
    # デフォルトの初期状態をセット
    st.session_state['toggle_photo'] = False   # ワークなし(LOW)
    st.session_state['toggle_sw'] = False      # 通常状態(LOW)
    st.session_state['toggle_magnet'] = False  # 【修正】初期状態は「磁気なし(OFF)」
    st.session_state['initialized'] = True

# メインモジュールのインポート（これだけで無限ループは起動しなくなります）
import typeM001_gpiozero as main

st.title("M001 シミュレータ")
st.write("物理配線モデル(LED、モーター、各種センサー)を画面上に再現します。")
st.markdown("---")

# --- サイドバー：シナリオテスト実行パネル ---
st.sidebar.header("シナリオテスト実行")
st.sidebar.write("各ボタンを押すと、pytestのシナリオと同等の入力を再現します。")

if st.sidebar.button("シナリオ01: 正常運転"):
    st.session_state['toggle_photo'] = True   # HIGH: ワーク検知
    st.session_state['toggle_sw'] = False     # LOW: 通常
    st.session_state['toggle_magnet'] = False # 【修正】OFF = 磁気なし
    st.rerun()

if st.sidebar.button("シナリオ02: 磁気検知"):
    st.session_state['toggle_photo'] = True   # HIGH: ワーク検知
    st.session_state['toggle_sw'] = False     # LOW: 通常
    st.session_state['toggle_magnet'] = True  # 【修正】ON = 磁気検知
    st.rerun()

if st.sidebar.button("シナリオ03: 非常停止"):
    st.session_state['toggle_photo'] = True   # HIGH
    st.session_state['toggle_sw'] = True      # HIGH: 非常停止発動
    st.session_state['toggle_magnet'] = False # 【修正】OFF = 磁気なし
    st.rerun()

if st.sidebar.button("シナリオ04: 起動直後"):
    st.session_state['toggle_photo'] = False  # LOW: ワークなし
    st.session_state['toggle_sw'] = False     # LOW: 通常
    st.session_state['toggle_magnet'] = False # 【修正】OFF = 磁気なし
    st.rerun()

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
    # 【修正】ラベルのON/OFFの意味を直感的に「ON = 磁気検知」に変更
    st.toggle("磁気センサ (Pin 6) \n[ON = 磁気検知]", key="toggle_magnet")

# ==== 画面のトグル状態を実際のMockピンの状態へ反映 ====
if st.session_state['toggle_photo']:
    main.photo.pin.drive_high()  # current_photo = 1 (ワーク検知)
else:
    main.photo.pin.drive_low()   # current_photo = 0 (ワークなし)

if st.session_state['toggle_sw']:
    main.sw.pin.drive_high()     # current_sw = 1 (!!非常停止中!!)
else:
    main.sw.pin.drive_low()      # current_sw = 0 (解除/正常)

# 【修正】磁気センサの見た目ON/OFFをロジック（HIGH/LOW）と逆にドライブさせる
if st.session_state['toggle_magnet']:
    main.magnet.pin.drive_low()   # 画面ONのとき: drive_low() -> current_magnet = 0 (磁気検知状態へ)
else:
    main.magnet.pin.drive_high()  # 画面OFFのとき: drive_high() -> current_magnet = 1 (磁気なし状態へ)


# メインロジックを1ステップ実行して、アクチュエータの状態を更新
main.control_logic()

st.markdown("---")

# --- 出力側のUI ---
st.header("アクチュエータ / LED出力 (Pin 22, 23, 25)")
out_col1, out_col2, out_col3 = st.columns(3)

with out_col1:
    st.subheader("LED 01 (Pin 23)")
    st.caption("フォトセンサ用投光器")
    if main.led01.is_active:
        st.success("点灯中 (HIGH)")
    else:
        st.error("消灯 (LOW)")

with out_col2:
    st.subheader("モーター (Pin 22)")
    st.caption("コンベア等の駆動")
    if main.motor.is_active:
        st.success("回転中 (HIGH)")
    else:
        st.error("停止 (LOW)")

with out_col3:
    st.subheader("LED 02 (Pin 25)")
    st.caption("ステータスランプ")
    if main.led02.is_active:
        st.success("点灯中 (HIGH)")
    else:
        st.error("消灯 (LOW)")