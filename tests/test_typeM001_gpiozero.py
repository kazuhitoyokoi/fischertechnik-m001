import sys
import os
from pathlib import Path
import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPin

# pytestのimportモード差異に依存せず、常にプロジェクトルートを解決する
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ==== 1. PWMエラー回避パッチ ====
def mock_set_frequency(self, value):
    pass
MockPin._set_frequency = mock_set_frequency

# ==== 2. gpiozero モック設定 ====
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'
Device.pin_factory = MockFactory()

@pytest.fixture(autouse=True)
def clean_environment():
    if "typeM001_gpiozero" in sys.modules:
        del sys.modules["typeM001_gpiozero"]
    Device.pin_factory.reset()
    yield
    if "typeM001_gpiozero" in sys.modules:
        del sys.modules["typeM001_gpiozero"]
    Device.pin_factory.reset()

# ==========================================================================================
# テストシナリオ群
# ==========================================================================================
# 【対応表】
# 本体ロジックの判定に合わせるため、以下のようにピンをドライブします：
# ・ワーク検知 (1) にしたい場合 -> drive_high() (is_active=False -> current_photo=1)
# ・ワークなし (0) にしたい場合 -> drive_low()  (is_active=True -> current_photo=0)
# ・非常停止中 (1) にしたい場合 -> drive_high() (is_active=False -> current_sw=1)
# ・通常状態/解除 (0) にしたい場合 -> drive_low()  (is_active=True -> current_sw=0)
# ・磁気なし (1) にしたい場合   -> drive_high() (is_active=False -> current_magnet=1)
# ・磁気検知 (0) にしたい場合   -> drive_low()  (is_active=True -> current_magnet=0)
# ==========================================================================================

def test_scenario_01_normal_conveyor():
    """正常運転: 非常停止解除(0) ＆ ワーク検知(1) ＆ 磁気なし(1) -> モーター回転"""
    import typeM001_gpiozero as main
    
    # 入力状態の模擬
    main.photo.pin.drive_high()   # current_photo = 1 (ワーク検知！)
    main.sw.pin.drive_low()       # current_sw = 0 (解除/正常)
    main.magnet.pin.drive_high()  # current_magnet = 1 (磁気なし)
    
    # 制御ロジックの1ステップ実行
    main.control_logic()
    
    # 検証
    assert main.motor.is_active is True


def test_scenario_02_magnet_detected():
    """磁気検知: モーター停止, LED点灯"""
    import typeM001_gpiozero as main
    
    # ワークがあり(1)、非常停止は通常(0)だが、磁気を検知(0)した状態を模擬
    main.photo.pin.drive_high()   # current_photo = 1 (ワーク検知！)
    main.sw.pin.drive_low()       # current_sw = 0 (解除/正常)
    main.magnet.pin.drive_low()   # current_magnet = 0 (磁気検知)
    
    main.control_logic()
    
    assert main.motor.is_active is False
    assert main.led02.is_active is True


def test_scenario_03_emergency_stop():
    """非常停止: スイッチが押されたら最優先でモーター停止"""
    import typeM001_gpiozero as main
    
    # ワークがあり(1)、磁気もない(1)が、非常停止が押された(1)状態を模擬
    main.photo.pin.drive_high()   # current_photo = 1 (ワーク検知！)
    main.sw.pin.drive_high()      # current_sw = 1 (!!非常停止中!!)
    main.magnet.pin.drive_high()  # current_magnet = 1 (磁気なし)
    
    main.control_logic()
    
    assert main.motor.is_active is False


def test_scenario_04_initial_state():
    """起動直後: ワークなしで停止していること"""
    import typeM001_gpiozero as main
    
    # 起動直後のデフォルト状態 (ワークなし0, 非常停止なし0, 磁気なし1)
    main.photo.pin.drive_low()    # current_photo = 0 (ワークなし)
    main.sw.pin.drive_low()       # current_sw = 0 (解除/正常)
    main.magnet.pin.drive_high()  # current_magnet = 1 (磁気なし)
    
    main.control_logic()
    
    assert main.motor.is_active is False
    assert main.led02.is_active is False


def test_scenario_05_keep_running_after_passing_work():
    """状態保持: ワークが通り過ぎても回転を保持すること"""
    import typeM001_gpiozero as main
    
    # 1. まずワークが乗ってモーターが起動する(シナリオ01の状態)
    main.photo.pin.drive_high()   # current_photo = 1 (ワーク検知！)
    main.sw.pin.drive_low()       # current_sw = 0 (解除/正常)
    main.magnet.pin.drive_high()  # current_magnet = 1 (磁気なし)
    main.control_logic()
    assert main.motor.is_active is True
    
    # 2. 次のステップでワークが通り過ぎてフォトセンサがOFF(0)になる
    main.photo.pin.drive_low()    # current_photo = 0 (ワークなし)
    main.control_logic()
    
    # 3. ワークが離れても自己保持でモーターが回転し続けていることを検証
    assert main.motor.is_active is True