import json
import os
import time
import signal
import logging

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações — Modbus
MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))
INTERVALO = int(os.getenv("INTERVALO", "5"))

# Configurações — MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1884"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "modbus/factory/sensors")

# Logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


class ModbusClient:
    """Cliente que lê registros Modbus e publica via MQTT."""

    def __init__(self):
        self.stop = False
        self.modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        self.mqtt_client = mqtt.Client(client_id="modbus-client-pub")
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info("Sinal %s recebido, encerrando cliente...", signum)
        self.stop = True

    # ---------- Modbus ----------
    def connect_modbus(self):
        while not self.stop and not self.modbus_client.connect():
            log.warning(
                "Não foi possível conectar ao Modbus %s:%s, tentando novamente...",
                MODBUS_HOST,
                MODBUS_PORT,
            )
            time.sleep(5)
        log.info("Conectado ao servidor Modbus %s:%s", MODBUS_HOST, MODBUS_PORT)

    # ---------- MQTT ----------
    def connect_mqtt(self):
        while not self.stop:
            try:
                self.mqtt_client.connect(MQTT_HOST, MQTT_PORT)
                self.mqtt_client.loop_start()
                log.info("Conectado ao broker MQTT %s:%s", MQTT_HOST, MQTT_PORT)
                return
            except Exception as exc:
                log.warning("MQTT indisponível (%s), tentando novamente...", exc)
                time.sleep(5)

    def read_registers(self):
        result = self.modbus_client.read_holding_registers(address=0, count=3, slave=1)
        if result.isError():
            log.error("Erro ao ler Modbus: %s", result)
            return None
        return {
            "temperature": round(result.registers[0] / 10.0, 1),
            "pressure": round(result.registers[1] / 10.0, 1),
            "machine_state": result.registers[2],
            "timestamp": int(time.time()),
        }

    def run(self):
        self.connect_modbus()
        self.connect_mqtt()
        log.info(
            "Iniciando loop de leitura a cada %s segundos — publicar em '%s'",
            INTERVALO,
            MQTT_TOPIC,
        )
        while not self.stop:
            payload = self.read_registers()
            if payload:
                msg = json.dumps(payload)
                self.mqtt_client.publish(MQTT_TOPIC, msg)
                log.info("[MQTT] Publicado em '%s': %s", MQTT_TOPIC, msg)
            time.sleep(INTERVALO)
        self.shutdown()

    def shutdown(self):
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except Exception:
            pass
        try:
            self.modbus_client.close()
        except Exception:
            pass
        log.info("Cliente encerrado.")


if __name__ == "__main__":
    client = ModbusClient()
    try:
        client.run()
    finally:
        client.shutdown()

