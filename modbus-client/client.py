import os
import json
import time
import signal
import logging

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações
MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1884"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "modbus/factory/sensors")
INTERVALO = int(os.getenv("INTERVALO", "5"))

# Logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

class ModbusMqttClient:
    """Cliente que lê registros Modbus e publica no MQTT.

    - Reconexão automática para Modbus e MQTT.
    - Captura de SIGINT/SIGTERM para encerramento gracioso.
    - Configurações carregadas a partir de .env.
    """

    def __init__(self):
        self.stop = False
        self.modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        self.mqtt_client = mqtt.Client(client_id="modbus-client")
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info("Sinal %s recebido, encerrando cliente...", signum)
        self.stop = True
        self.shutdown()

    # ---------- MQTT ----------
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("Conectado ao broker MQTT %s:%s", MQTT_HOST, MQTT_PORT)
        else:
            log.error("Falha ao conectar ao broker MQTT, rc=%s", rc)

    def connect_mqtt(self):
        while True:
            try:
                self.mqtt_client.connect(MQTT_HOST, MQTT_PORT)
                self.mqtt_client.loop_start()
                break
            except Exception as exc:
                log.warning("Erro ao conectar ao MQTT, tentando novamente: %s", exc)
                time.sleep(5)

    # ---------- Modbus ----------
    def connect_modbus(self):
        while not self.modbus_client.connect():
            log.warning("Não foi possível conectar ao Modbus %s:%s, tentando novamente...", MODBUS_HOST, MODBUS_PORT)
            time.sleep(5)
        log.info("Conectado ao servidor Modbus %s:%s", MODBUS_HOST, MODBUS_PORT)

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

    def publish(self, payload: dict):
        try:
            self.mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
            log.info("Publicado no MQTT tópico %s: %s", MQTT_TOPIC, payload)
        except Exception as exc:
            log.error("Falha ao publicar no MQTT: %s", exc)

    def run(self):
        self.connect_mqtt()
        self.connect_modbus()
        log.info("Iniciando loop de leitura a cada %s segundos", INTERVALO)
        while not self.stop:
            payload = self.read_registers()
            if payload:
                self.publish(payload)
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
    client = ModbusMqttClient()
    client.run()
