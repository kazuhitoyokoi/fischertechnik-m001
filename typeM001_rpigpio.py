import os
from dataclasses import dataclass
from gpiozero import LED, Motor, Button
import time

# ピン配置の設定
LED01_PIN = 23
MOTOR_PIN = 22
MOTOR_DUMMY_BACKWARD_PIN = 24
LED02_PIN = 25

PHOTO_PIN = 5
MAGNET_PIN = 6
SW_PIN = 16
LOOP_INTERVAL_SEC = 0.05

# GPIO初期設定
led01 = LED(LED01_PIN)
led02 = LED(LED02_PIN)
motor = Motor(forward=MOTOR_PIN, backward=MOTOR_DUMMY_BACKWARD_PIN) # 逆転用はダミーピン24

# プルアップ設定のみ指定
photo = Button(PHOTO_PIN, pull_up=True)
magnet = Button(MAGNET_PIN, pull_up=True)
sw = Button(SW_PIN, pull_up=True)

# 初期出力
led01.on()
print("== START ==")
print("CTRL+C = END")
print("システム監視を開始しました...")

prev_photo = None
prev_sw = None
prev_magnet = None
prev_motor = False # LOW相当
prev_led02 = False # LOW相当


@dataclass
class InputState:
    photo: int
    sw: int
    magnet: int


def _read_inputs():
    return InputState(
        photo=0 if photo.is_active else 1,
        sw=0 if sw.is_active else 1,
        magnet=0 if magnet.is_active else 1,
    )


def _log_input_changes(state):
    global prev_photo, prev_sw, prev_magnet

    if state.photo != prev_photo:
        print(f"[入力変化] フォトセンサ (GPIO {PHOTO_PIN}): {'HIGH (ワーク検知！)' if state.photo == 1 else 'LOW (ワークなし)'}")
        prev_photo = state.photo

    if state.sw != prev_sw:
        print(f"[入力変化] 非常停止スイッチ (GPIO {SW_PIN}): {'HIGH (!!非常停止中!!)' if state.sw == 1 else 'LOW (解除/正常)'}")
        prev_sw = state.sw

    if state.magnet != prev_magnet:
        print(f"[入力変化] 磁気センサ (GPIO {MAGNET_PIN}): {'LOW (磁気検知)' if state.magnet == 0 else 'HIGH (磁気なし)'}")
        prev_magnet = state.magnet

def control_logic():
    """1ステップ分のロジック処理"""
    global prev_motor, prev_led02

    state = _read_inputs()
    _log_input_changes(state)

    # ---- 2. ロジック処理と出力制御 ----
    # 【最優先】非常停止ボタンが押されている(1)間は強制停止
    if state.sw == 1:
        if prev_motor is not False:
            print(f"[警報] 非常停止が作動中のため、モーター (GPIO {MOTOR_PIN}) を強制停止しています。")
            prev_motor = False
        motor.stop()
        
    else:
        # ワークを検知（1）したらコンベア（モーター）を開始
        if state.photo == 1:
            if prev_motor is not True:
                print(f"[制御] 非常停止解除／ワーク検知により、モーター (GPIO {MOTOR_PIN}) を起動します。")
                prev_motor = True
            motor.forward()

        # 磁気センサ(0)を検知したらコンベア（モーター）を停止し、LED02を点灯
        if state.magnet == 0:
            if prev_motor is not False:
                print(f"[制御] 磁気を検知したため、モーター (GPIO {MOTOR_PIN}) を停止します。")
                prev_motor = False
            motor.stop()
            
            if prev_led02 is not True:
                print(f"[出力変化] LED02 (GPIO {LED02_PIN}): HIGH (点灯)")
                prev_led02 = True
            led02.on()
        else:
            if prev_led02 is not False:
                print(f"[出力変化] LED02 (GPIO {LED02_PIN}): LOW (消灯)")
                prev_led02 = False
            led02.off()


def run_forever():
    try:
        while True:
            control_logic()
            time.sleep(LOOP_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n== END ==")

# Streamlitから実行されている場合は無限ループさせない
if os.environ.get('STREAMLIT_RUNNING') != '1':
    run_forever()
