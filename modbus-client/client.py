import json
import os
import time

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient

MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1884"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "modbus/factory/sensors")

INTERVALO = int(os.getenv("INTERVALO", "5"))


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[Cliente MQTT] Ligado ao broker {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[Cliente MQTT] Erro de ligação, código: {rc}")


# Ligação MQTT
mqtt_client = mqtt.Client(client_id="modbus-client")
mqtt_client.on_connect = on_connect
mqtt_client.connect(MQTT_HOST, MQTT_PORT)
mqtt_client.loop_start()

# Ligação Modbus
modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
if modbus_client.connect():
    print(f"[Cliente Modbus] Ligado ao servidor {MODBUS_HOST}:{MODBUS_PORT}")
else:
    print(f"[Cliente Modbus] ERRO: Não foi possível ligar a {MODBUS_HOST}:{MODBUS_PORT}")
    exit(1)

print(f"[Cliente] A ler registos a cada {INTERVALO}s ...\n")

# -------------------------------------------------------------------
# Loop principal de leitura e publicação
# -------------------------------------------------------------------
while True:
    result = modbus_client.read_holding_registers(address=0, count=3, slave=1)

    if not result.isError():
        payload = {
            "temperature": round(result.registers[0] / 10.0, 1),
            "pressure": round(result.registers[1] / 10.0, 1),
            "machine_state": result.registers[2],
            "timestamp": int(time.time()),
        }
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"[Cliente] Publicado em '{MQTT_TOPIC}' -> {payload}")
    else:
        print(f"[Cliente] Erro ao ler Modbus: {result}")

    time.sleep(INTERVALO)
