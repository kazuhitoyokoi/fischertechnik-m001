import time
from opcua import Client

# Raspberry Piの実際のIPアドレスに書き換えてください
url = "opc.tcp://172.20.10.2:4840/m001"

client = Client(url)
client.connect()

ns = client.get_namespace_index("urn:local:l1")
objects = client.get_objects_node()

nodes = [
    objects.get_child([f"{ns}:Sensors", f"{ns}:PhotoSensor"]),
    objects.get_child([f"{ns}:Sensors", f"{ns}:PushSwitch"]),
    objects.get_child([f"{ns}:Sensors", f"{ns}:MagnetSensor"]),
    objects.get_child([f"{ns}:Actuators", f"{ns}:ProjectorLED"]),
    objects.get_child([f"{ns}:Actuators", f"{ns}:ConveyorMotor"]),
    objects.get_child([f"{ns}:Actuators", f"{ns}:StatusLED"])
]

# 前回の値を記憶しておくための辞書
prev_values = {}

while True:
    for node in nodes:
        current_value = node.get_value()
        node_id = node.nodeid.to_string()
        
        # 初回の取得、または前回の値から変化した場合のみ表示する
        if node_id not in prev_values or prev_values[node_id] != current_value:
            node_name = node.get_browse_name().Name
            print(f"[{node_id}] {node_name} : {current_value}")
            
            # 現在の値を「前回の値」として更新
            prev_values[node_id] = current_value
            
    time.sleep(0.5)
