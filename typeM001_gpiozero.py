from gpiozero import LED, Motor, Button
import time
import os

# ピン配置の設定
led01_pin = 23
motor_pin = 22
led02_pin = 25

photo_pin = 5
magnet_pin = 6
sw_pin = 16

# GPIO初期設定
led01 = LED(led01_pin)
led02 = LED(led02_pin)

# === 【重要】実機でPWMエラーを出さないための設定 ===
# 速度制御（PWM）を使わない単純なON/OFFモーターとして初期化します。
# これにより、バックエンドライブラリを問わず「PinPWMUnsupported」エラーを完全に回避できます。
motor = Motor(forward=motor_pin, backward=24, pwm=False) 

# プルアップ設定のみ指定
photo = Button(photo_pin, pull_up=True)
magnet = Button(magnet_pin, pull_up=True)
sw = Button(sw_pin, pull_up=True)

# 初期出力
led01.on()

prev_photo = None
prev_sw = None
prev_magnet = None
prev_motor = False # LOW相当
prev_led02 = False # LOW相当

def control_logic():
    """1回分の制御ロジックを実行する関数（Streamlitやテストから再利用）"""
    global prev_photo, prev_sw, prev_magnet, prev_motor, prev_led02

    # 現在の入力を取得
    current_photo = 0 if photo.is_active else 1
    current_sw = 0 if sw.is_active else 1
    current_magnet = 0 if magnet.is_active else 1

    # ---- 1. 入力状態の変化をログ出力 ----
    if current_photo != prev_photo:
        print(f"[入力変化] フォトセンサ (GPIO {photo_pin}): {'HIGH (ワーク検知！)' if current_photo == 1 else 'LOW (ワークなし)'}")
        prev_photo = current_photo

    if current_sw != prev_sw:
        print(f"[入力変化] 非常停止スイッチ (GPIO {sw_pin}): {'HIGH (!!非常停止中!!)' if current_sw == 1 else 'LOW (解除/正常)'}")
        prev_sw = current_sw

    if current_magnet != prev_magnet:
        print(f"[入力変化] 磁気センサ (GPIO {magnet_pin}): {'LOW (磁気検知)' if current_magnet == 0 else 'HIGH (磁気なし)'}")
        prev_magnet = current_magnet

    # ---- 2. ロジック処理と出力制御 ----
    
    # 【最優先】非常停止ボタンが押されている(1)間は強制停止
    if current_sw == 1:
        if prev_motor != False:
            print(f"[警報] 非常停止が作動中のため、モーター (GPIO {motor_pin}) を強制停止しています。")
            prev_motor = False
        motor.stop()
        
    else:
        # ワークを検知（1）したらコンベア（モーター）を開始
        if current_photo == 1:
            if prev_motor != True:
                print(f"[制御] 非常停止解除／ワーク検知により、モーター (GPIO {motor_pin}) を起動します。")
                prev_motor = True
            motor.forward()

        # 磁気センサ(0)を検知したらコンベア（モーター）を停止し、LED02を点灯
        if current_magnet == 0:
            if prev_motor != False:
                print(f"[制御] 磁気を検知したため、モーター (GPIO {motor_pin}) を停止します。")
                prev_motor = False
            motor.stop()
            
            if prev_led02 != True:
                print(f"[出力変化] LED02 (GPIO {led02_pin}): HIGH (点灯)")
                prev_led02 = True
            led02.on()
        else:
            if prev_led02 != False:
                print(f"[出力変化] LED02 (GPIO {led02_pin}): LOW (消灯)")
                prev_led02 = False
            led02.off()

# 直接 python typeM001_gpiozero.py として実行された（実機モード）時だけ無限ループを回す
if __name__ == '__main__':
    print("== START ==")
    print("CTRL+C = END")
    print("システム監視を開始しました...(実機物理ピン制御モード)")
    try:
        while True:
            control_logic()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n== END ==")