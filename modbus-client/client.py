import os
import time
import signal
import logging

from pymodbus.client import ModbusTcpClient
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações
MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))
INTERVALO = int(os.getenv("INTERVALO", "5"))

# Logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


class ModbusClient:
    """Cliente que lê registros Modbus (apenas leitura)."""

    def __init__(self):
        self.stop = False
        self.modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info("Sinal %s recebido, encerrando cliente...", signum)
        self.stop = True
        self.shutdown()

    # ---------- Modbus ----------
    def connect_modbus(self):
        while not self.modbus_client.connect():
            log.warning(
                "Não foi possível conectar ao Modbus %s:%s, tentando novamente...",
                MODBUS_HOST,
                MODBUS_PORT,
            )
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

    def run(self):
        self.connect_modbus()
        log.info("Iniciando loop de leitura a cada %s segundos", INTERVALO)
        while not self.stop:
            payload = self.read_registers()
            if payload:
                log.info("Leitura Modbus: %s", payload)
            time.sleep(INTERVALO)
        self.shutdown()

    def shutdown(self):
        try:
            self.modbus_client.close()
        except Exception:
            pass
        log.info("Cliente encerrado.")


if __name__ == "__main__":
    client = ModbusClient()
    client.run()
