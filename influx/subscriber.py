import json
import os
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import yaml
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# CONFIG_FILE e opcional; variaveis de ambiente tem prioridade sobre o ficheiro
CONFIG_FILE = os.getenv("CONFIG_FILE", "")


def load_file_config():
    if not CONFIG_FILE or not os.path.exists(CONFIG_FILE):
        return {}

    with open(CONFIG_FILE, "r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle) or {}


def resolve_settings():
    file_config = load_file_config()
    mqtt_config = file_config.get("mqtt", {})
    influx_config = file_config.get("influxdb", {})

    return {
        "mqtt_host": os.getenv("MQTT_HOST", mqtt_config.get("host", "localhost")),
        "mqtt_port": int(os.getenv("MQTT_PORT", mqtt_config.get("port", 1884))),
        "mqtt_topic": os.getenv("MQTT_TOPIC", mqtt_config.get("topic", "modbus/factory/sensors")),
        "influx_url": os.getenv("INFLUX_URL", influx_config.get("url", "http://localhost:8086")),
        "influx_token": os.getenv("INFLUX_TOKEN", influx_config.get("token", "edgex-influx-token-2024")),
        "influx_org": os.getenv("INFLUX_ORG", influx_config.get("org", "edgex-org")),
        "influx_bucket": os.getenv("INFLUX_BUCKET", influx_config.get("bucket", "factory")),
        "influx_measurement": os.getenv(
            "INFLUX_MEASUREMENT",
            influx_config.get("measurement", "factory_sensors"),
        ),
    }


SETTINGS = resolve_settings()
MQTT_HOST = SETTINGS["mqtt_host"]
MQTT_PORT = SETTINGS["mqtt_port"]
MQTT_TOPIC = SETTINGS["mqtt_topic"]
INFLUX_URL = SETTINGS["influx_url"]
INFLUX_TOKEN = SETTINGS["influx_token"]
INFLUX_ORG = SETTINGS["influx_org"]
INFLUX_BUCKET = SETTINGS["influx_bucket"]
INFLUX_MEASUREMENT = SETTINGS["influx_measurement"]


def build_write_api():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    return client, client.write_api(write_options=SYNCHRONOUS)


influx_client, write_api = build_write_api()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[Subscriber] Ligado ao broker MQTT {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"[Subscriber] Subscrito ao topico '{MQTT_TOPIC}'")
    else:
        print(f"[Subscriber] Erro de ligacao MQTT, codigo: {rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        temperature = float(payload["temperature"])
        pressure = float(payload["pressure"])
        machine_state = int(payload["machine_state"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"[Subscriber] Payload invalido: {exc}")
        return

    timestamp = payload.get("timestamp")
    if timestamp is None:
        event_time = datetime.now(timezone.utc)
    else:
        event_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)

    point = (
        Point(INFLUX_MEASUREMENT)
        .field("temperature", temperature)
        .field("pressure", pressure)
        .field("machine_state", machine_state)
        .time(event_time, WritePrecision.S)
    )

    try:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    except Exception as exc:
        print(f"[Subscriber] Erro ao gravar no InfluxDB: {exc}")
        return
    print(
        "[Subscriber] Gravado no InfluxDB -> "
        f"temp={temperature}C, "
        f"pressure={pressure}bar, "
        f"machine_state={machine_state}"
    )


def main():
    print(
        f"[Subscriber] A enviar dados para {INFLUX_URL} | "
        f"org={INFLUX_ORG} bucket={INFLUX_BUCKET}"
    )
    mqtt_client = mqtt.Client(client_id="modbus-subscriber")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_forever()


if __name__ == "__main__":
    try:
        main()
    finally:
        influx_client.close()
