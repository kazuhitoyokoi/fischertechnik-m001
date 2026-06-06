import os
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

import streamlit as st
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

st.set_page_config(page_title="システム シミュレータ", layout="wide")

# --- 初期化処理 ---
if 'initialized' not in st.session_state:
    Device.pin_factory = MockFactory()
    import main
    main.setup()
    
    # トグルウィジェットの初期状態をセット
    st.session_state['toggle_photo'] = True
    st.session_state['toggle_sw'] = True
    st.session_state['toggle_magnet'] = True
    st.session_state['initialized'] = True
else:
    import main

st.title("M001 シミュレータ")
st.write("物理配線モデル(LED、モーター、各種センサー)を画面上に再現")
st.markdown("---")

# --- サイドバー：シナリオテスト実行パネル ---
st.sidebar.header("シナリオテスト実行")
st.sidebar.write("各ボタンを押すと、test_main.py と同等のシナリオを画面上に再現します。")

if st.sidebar.button("シナリオ1: 全センサー通常 (HIGH)"):
    st.session_state['toggle_photo'] = True
    st.session_state['toggle_sw'] = True
    st.session_state['toggle_magnet'] = True
    st.sidebar.success("シナリオ1を適用しました。")

if st.sidebar.button("シナリオ2: 磁石検出 (LOW)"):
    st.session_state['toggle_photo'] = True
    st.session_state['toggle_sw'] = True
    st.session_state['toggle_magnet'] = False
    st.sidebar.success("シナリオ2を適用しました。")

if st.sidebar.button("シナリオ3: 光遮断 ＆ スイッチ押下 (LOW)"):
    st.session_state['toggle_photo'] = False
    st.session_state['toggle_sw'] = False
    st.session_state['toggle_magnet'] = True
    st.sidebar.success("シナリオ3を適用しました。")

st.markdown("---")

# --- 入力側のUI ---
st.header("センサー / スイッチ入力 (Pin 5, 6, 16)")
st.caption("※プルアップ回路のため、通常時(ON)が HIGH=1、遮断・押下時(OFF)が LOW=0 です。")

col1, col2, col3 = st.columns(3)

with col1:
    photo_high = st.toggle("フォトトランジスタ (Pin 5)", key="toggle_photo", help="光を受光しているとHIGH(1)、遮断されるとLOW(0)")

with col2:
    sw_high = st.toggle("プッシュスイッチ (Pin 16)", key="toggle_sw", help="押されていないとHIGH(1)、押すとLOW(0)")

with col3:
    magnet_high = st.toggle("磁気センサー (Pin 6)", key="toggle_magnet", help="磁石がないとHIGH(1)、磁石が来るとLOW(0)")

# 現在の確定値を実際のモックピンにドライブ
if st.session_state['toggle_photo']:
    Device.pin_factory.pin(5).drive_high()
else:
    Device.pin_factory.pin(5).drive_low()

if st.session_state['toggle_sw']:
    Device.pin_factory.pin(16).drive_high()
else:
    Device.pin_factory.pin(16).drive_low()

if st.session_state['toggle_magnet']:
    Device.pin_factory.pin(6).drive_high()
else:
    Device.pin_factory.pin(6).drive_low()

# main.py のロジックを実行
main.control_logic()

st.markdown("---")

# --- 出力側のUI ---
st.header("アクチュエータ / LED出力 (Pin 22, 23, 25)")
out_col1, out_col2, out_col3 = st.columns(3)

with out_col1:
    st.subheader("LED 01 (Pin 23)")
    st.caption("※フォトトランジスタ用投光器")
    if main.led01.is_active:
        st.success("点灯中 (HIGH)")
    else:
        st.error("消灯 (LOW)")

with out_col2:
    st.subheader("モーター (Pin 22)")
    st.caption("※コンベア等の駆動")
    if main.motor.is_active:
        st.success("回転中 (HIGH)")
    else:
        st.error("停止 (LOW)")

with out_col3:
    st.subheader("LED 02 (Pin 25)")
    st.caption("※ステータスランプ")
    if main.led02.is_active:
        st.success("点灯中 (HIGH)")
    else:
        st.error("消灯 (LOW)")