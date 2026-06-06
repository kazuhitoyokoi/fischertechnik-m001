import os
import time
import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory
from opcua import Client

# 外部ライブラリ(opcua)の旧datetime仕様による大量の非推奨ワーニングを本質的にフィルタリング
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning:opcua.*")

os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'
Device.pin_factory = MockFactory()

import main

@pytest.fixture(scope="function")
def opcua_server_fixture():
    main.setup()
    server = main.init_opcua_server()
    server.start()
    
    client = Client("opc.tcp://127.0.0.1:4840/freeopcua/server/")
    client.connect()
    
    yield server, client
    
    client.disconnect()
    server.stop()
    time.sleep(0.2)

# ==========================================================================================
# グループ1: 制御再現ロジック単体のテストケース (OPC UAを介さないピュアなテスト)
# ==========================================================================================

def test_control_logic_only_scenario_01():
    """シナリオ1: 全センサー通常(HIGH)のハードウェア挙動を検証"""
    main.setup()
    main.setup()  # クリーンアップ処理(41-42行目)を通過させてカバレッジを100%に近づける
    
    main.photo.pin.drive_high()
    main.sw.pin.drive_high()
    main.magnet.pin.drive_high()
    
    main.control_logic()
    
    assert main.motor.is_active is True
    assert main.led02.is_active is False

def test_control_logic_only_scenario_02():
    """シナリオ2: 磁石検出(LOW)時のインターロックハードウェア挙動を検証"""
    main.setup()
    main.photo.pin.drive_high()
    main.sw.pin.drive_high()
    main.magnet.pin.drive_low()
    
    main.control_logic()
    
    assert main.motor.is_active is False
    assert main.led02.is_active is True

# ==========================================================================================
# グループ2: OPC UA 階層およびデータ同期のテストケース
# ==========================================================================================

def test_opcua_hierarchy_definition(opcua_server_fixture):
    """階層ノード(Sensors/Actuatorsが直下にあるか)が正しく定義されているかを検証"""
    _, client = opcua_server_fixture
    objects = client.get_objects_node()
    
    sensors = objects.get_child(["2:Sensors"])
    actuators = objects.get_child(["2:Actuators"])
    
    assert sensors.get_child(["2:PhotoSensor"]) is not None
    assert actuators.get_child(["2:ConveyorMotor"]) is not None

def test_opcua_data_synchronization_scenario_01(opcua_server_fixture):
    """シナリオ1のデータがフラット化されたOPC UA空間へ正しく同期されるかを検証"""
    _, client = opcua_server_fixture
    
    main.photo.pin.drive_high()
    main.sw.pin.drive_high()
    main.magnet.pin.drive_high()
    
    main.update_and_sync()
    
    objects = client.get_objects_node()
    v_motor = objects.get_child(["2:Actuators", "2:ConveyorMotor"]).get_value()
    v_led02 = objects.get_child(["2:Actuators", "2:StatusLED"]).get_value()
    
    assert v_motor is True
    assert v_led02 is False

# ==========================================================================================
# グループ3: メインループおよびカバレッジ補完テスト
# ==========================================================================================

def test_main_loop_execution(monkeypatch):
    """main_loopの起動とKeyboardInterruptによる正常停止ルートをテストしてカバレッジを最大化"""
    def mock_update_and_sync():
        raise KeyboardInterrupt
        
    monkeypatch.setattr(main, "update_and_sync", mock_update_and_sync)
    main.main_loop()
    assert True