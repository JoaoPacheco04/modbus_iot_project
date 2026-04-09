import json
import logging
import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import yaml
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

CONFIG_FILE = os.getenv("CONFIG_FILE", "")


def load_file_config():
    if not CONFIG_FILE or not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_settings():
    fc = load_file_config()
    mqtt_c = fc.get("mqtt", {})
    inf_c = fc.get("influxdb", {})
    return {
        "mqtt_host":          os.getenv("MQTT_HOST",          mqtt_c.get("host", "localhost")),
        "mqtt_port":      int(os.getenv("MQTT_PORT",          mqtt_c.get("port", 1884))),
        "mqtt_topic":         os.getenv("MQTT_TOPIC",         mqtt_c.get("topic", "edgex/factory/sensors")),
        "influx_url":         os.getenv("INFLUX_URL",         inf_c.get("url",   "http://localhost:8086")),
        "influx_token":       os.getenv("INFLUX_TOKEN",       inf_c.get("token", "")),
        "influx_org":         os.getenv("INFLUX_ORG",         inf_c.get("org",   "edgex-org")),
        "influx_bucket":      os.getenv("INFLUX_BUCKET",      inf_c.get("bucket", "factory")),
        "influx_measurement": os.getenv("INFLUX_MEASUREMENT", inf_c.get("measurement", "factory_sensors")),
    }


def parse_edgex_payload(payload: dict) -> dict | None:
    """Parseia o formato EdgeX Event.

    {
        "deviceName": "modbus-factory-device",
        "origin": 1234567890000000000,
        "readings": [
            {"resourceName": "temperature",   "value": "25.3"},
            {"resourceName": "pressure",      "value": "4.1"},
            {"resourceName": "machine_state", "value": "1"}
        ]
    }
    """
    try:
        readings = {r["resourceName"]: r["value"] for r in payload.get("readings", [])}
        temperature   = float(readings["temperature"])
        pressure      = float(readings["pressure"])
        machine_state = int(float(readings["machine_state"]))
        origin_ns     = payload.get("origin")
        event_time    = (
            datetime.fromtimestamp(origin_ns / 1e9, tz=timezone.utc)
            if origin_ns
            else datetime.now(timezone.utc)
        )
        return {
            "temperature":   temperature,
            "pressure":      pressure,
            "machine_state": machine_state,
            "event_time":    event_time,
            "device":        payload.get("deviceName", "unknown"),
        }
    except (KeyError, TypeError, ValueError):
        return None


def parse_simple_payload(payload: dict) -> dict | None:
    """Parseia o formato simples do modbus-client Python.

    {"temperature": 25.3, "pressure": 4.1, "machine_state": 1, "timestamp": 1234567890}
    """
    try:
        temperature   = float(payload["temperature"])
        pressure      = float(payload["pressure"])
        machine_state = int(payload["machine_state"])
        ts            = payload.get("timestamp")
        event_time    = (
            datetime.fromtimestamp(ts, tz=timezone.utc)
            if ts is not None
            else datetime.now(timezone.utc)
        )
        return {
            "temperature":   temperature,
            "pressure":      pressure,
            "machine_state": machine_state,
            "event_time":    event_time,
            "device":        "modbus-client-python",
        }
    except (KeyError, TypeError, ValueError):
        return None


class InfluxSubscriber:

    def __init__(self, settings: dict):
        self.s = settings
        self.influx_client = None
        self.write_api = None
        self.mqtt_client = mqtt.Client(client_id="modbus-subscriber")
        self.mqtt_client.on_connect    = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message    = self._on_message

    # ------------------------------------------------------------------
    # InfluxDB
    # ------------------------------------------------------------------
    def _connect_influx(self):
        while True:
            try:
                client = InfluxDBClient(
                    url=self.s["influx_url"],
                    token=self.s["influx_token"],
                    org=self.s["influx_org"],
                )
                client.ping()
                self.influx_client = client
                self.write_api = client.write_api(write_options=SYNCHRONOUS)
                log.info("Ligado ao InfluxDB %s", self.s["influx_url"])
                return
            except Exception as exc:
                log.warning("InfluxDB indisponível, a tentar novamente: %s", exc)
                time.sleep(5)

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("Ligado ao broker MQTT %s:%s", self.s["mqtt_host"], self.s["mqtt_port"])
            topics = [t.strip() for t in self.s["mqtt_topic"].split(",")]
            for topic in topics:
                client.subscribe(topic)
                log.info("Subscrito ao tópico '%s'", topic)
        else:
            log.error("Erro de ligação MQTT, código: %s", rc)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning("Desligado inesperadamente do broker MQTT (rc=%s), a reconectar...", rc)
            self._reconnect_mqtt()

    def _reconnect_mqtt(self):
        while True:
            try:
                self.mqtt_client.reconnect()
                log.info("Reconectado ao broker MQTT")
                return
            except Exception as exc:
                log.warning("Falha na reconexão MQTT: %s — a tentar novamente em 5s", exc)
                time.sleep(5)

    # ------------------------------------------------------------------
    # Processamento de mensagens
    # ------------------------------------------------------------------
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            log.error("JSON inválido: %s", exc)
            return

        data   = parse_edgex_payload(payload)
        source = "EdgeX"
        if data is None:
            data   = parse_simple_payload(payload)
            source = "Python"
        if data is None:
            log.warning("Payload não reconhecido no tópico '%s': %s", msg.topic, payload)
            return

        point = (
            Point(self.s["influx_measurement"])
            .tag("device", data["device"])
            .tag("source", source)
            .field("temperature",   data["temperature"])
            .field("pressure",      data["pressure"])
            .field("machine_state", data["machine_state"])
            .time(data["event_time"], WritePrecision.S)
        )

        try:
            self.write_api.write(
                bucket=self.s["influx_bucket"],
                org=self.s["influx_org"],
                record=point,
            )
            log.info(
                "[%s] Gravado -> temp=%.1fC  pressure=%.1fbar  state=%d  device=%s",
                source,
                data["temperature"],
                data["pressure"],
                data["machine_state"],
                data["device"],
            )
        except Exception as exc:
            log.error("Erro ao gravar no InfluxDB: %s", exc)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def run(self):
        log.info(
            "A iniciar subscriber | InfluxDB: %s | org=%s bucket=%s",
            self.s["influx_url"], self.s["influx_org"], self.s["influx_bucket"],
        )
        self._connect_influx()
        self.mqtt_client.connect(self.s["mqtt_host"], self.s["mqtt_port"])
        self.mqtt_client.loop_forever()

    def close(self):
        if self.influx_client:
            self.influx_client.close()
        log.info("Subscriber encerrado.")


if __name__ == "__main__":
    sub = InfluxSubscriber(resolve_settings())
    try:
        sub.run()
    finally:
        sub.close()