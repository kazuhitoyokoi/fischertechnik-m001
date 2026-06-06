import os
import sys
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

if 'GPIOZERO_PIN_FACTORY' not in os.environ:
    os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

from gpiozero import LED, OutputDevice, Button
from opcua import Server, ua

led01 = None
motor = None
led02 = None
photo = None
magnet = None
sw = None

ua_photo = None
ua_sw = None
ua_magnet = None
ua_led01 = None
ua_motor = None
ua_led02 = None

def setup():
    global led01, motor, led02, photo, magnet, sw
    logger.info("setup() を開始します。各種デバイスを初期化します。")
    
    for dev in [led01, motor, led02, photo, magnet, sw]:
        if dev is not None:
            try:
                dev.close()
            except:
                pass

    led01 = LED(23)
    motor = OutputDevice(22)
    led02 = LED(25)

    photo = Button(5, pull_up=True)
    magnet = Button(6, pull_up=True)
    sw = Button(16, pull_up=True)
    
    led01.on()
    logger.info("setup() が完了しました。LED01(投光器): ON")

def control_logic():
    global led01, motor, led02, photo, magnet, sw
    
    p_val = int(photo.pin.state)
    s_val = int(sw.pin.state)
    m_val = int(magnet.pin.state)
    
    logger.info("control_logic() 実行 - 入力電位: フォト(Pin5)=%d, スイッチ(Pin16)=%d, 磁気(Pin6)=%d", p_val, s_val, m_val)

    if p_val == 1 and s_val == 1:
        if not motor.is_active:
            logger.info("条件一致: モーターを回転します (HIGH)")
        motor.on()

    if m_val == 0:
        if motor.is_active or not led02.is_active:
            logger.info("磁石検出: モーターを停止し、LED02(ステータス)を点灯します")
        motor.off()
        led02.on()
    else:
        if led02.is_active:
            logger.info("磁石なし: LED02(ステータス)を消灯します")
        led02.off()

    logger.info("control_logic() 終了 - 出力状態: LED01=%d, モーター=%d, LED02=%d", 
                1 if led01.is_active else 0, 1 if motor.is_active else 0, 1 if led02.is_active else 0)

def sync_to_opcua():
    global ua_photo, ua_sw, ua_magnet, ua_led01, ua_motor, ua_led02
    if ua_photo is not None:
        ua_photo.set_value(bool(photo.pin.state))
        ua_sw.set_value(bool(sw.pin.state))
        ua_magnet.set_value(bool(magnet.pin.state))
        
        ua_led01.set_value(bool(led01.is_active))
        ua_motor.set_value(bool(motor.is_active))
        ua_led02.set_value(bool(led02.is_active))

def update_and_sync():
    control_logic()
    sync_to_opcua()

def init_opcua_server():
    global ua_photo, ua_sw, ua_magnet, ua_led01, ua_motor, ua_led02
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    
    ns_node = server.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
    ns_node.set_value(["http://opcfoundation.org/UA/", "urn:local:l1", "urn:local:l2"])
    idx = 2
    
    logger.info("OPC UA サーバ名前空間をインデックス %d に固定しました", idx)

    objects = server.get_objects_node()
    
    # 階層L1〜L4を完全に廃止し、直接配下にフォルダを作成
    sensors_folder = objects.add_folder(idx, "Sensors")
    actuators_folder = objects.add_folder(idx, "Actuators")

    ua_photo = sensors_folder.add_variable(idx, "PhotoSensor", False)
    ua_sw = sensors_folder.add_variable(idx, "PushSwitch", False)
    ua_magnet = sensors_folder.add_variable(idx, "MagnetSensor", False)

    ua_led01 = actuators_folder.add_variable(idx, "ProjectorLED", False)
    ua_motor = actuators_folder.add_variable(idx, "ConveyorMotor", False)
    ua_led02 = actuators_folder.add_variable(idx, "StatusLED", False)

    ua_photo.set_writable()
    ua_sw.set_writable()
    ua_magnet.set_writable()

    return server

def main_loop():
    setup()
    server = init_opcua_server()
    
    logger.info("OPC UA サーバを起動します。")
    server.start()
    
    print("== START ==")
    print("CTRL+C = END")
    try:
        while True:
            update_and_sync()
            time.sleep(1)
    except KeyboardInterrupt:
        print("== END ==")
    finally:
        logger.info("OPC UA サーバを停止します。")
        server.stop()

if __name__ == "__main__":
    main_loop()