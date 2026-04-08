import os
import random
import threading
import time
import signal
import json
import logging
from dotenv import load_dotenv
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)

# Carrega variaveis de ambiente (.env) quando executado fora do Docker
load_dotenv()

# -------------------------------------------------------------------
# Configuracoes
# -------------------------------------------------------------------
MODBUS_HOST = os.getenv("MODBUS_HOST", "0.0.0.0")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))
REGISTERS_MAP_FILE = os.getenv("REGISTERS_MAP_FILE", "")

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Funções auxiliares
# -------------------------------------------------------------------
def load_registers_map():
    """Carrega o mapa de registros a partir de um arquivo JSON opcional.

    O JSON deve ser um dicionário onde a chave é o índice do registro
    (int) e o valor é o valor inicial (int). Se o arquivo não existir ou
    estiver vazio, usa o mapa padrão definido no código.
    """
    if REGISTERS_MAP_FILE and os.path.isfile(REGISTERS_MAP_FILE):
        try:
            with open(REGISTERS_MAP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            max_index = max(int(k) for k in data.keys())
            values = [0] * (max_index + 1)
            for k, v in data.items():
                values[int(k)] = int(v)
            return values
        except Exception as exc:
            log.warning("Falha ao ler REGISTERS_MAP_FILE %s: %s", REGISTERS_MAP_FILE, exc)
    return [250, 42, 1]

initial_registers = load_registers_map()
store = ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, initial_registers))
context = ModbusServerContext(slaves=store, single=True)

# -------------------------------------------------------------------
# Simulação de dados
# -------------------------------------------------------------------
def simular_dados(stop_event: threading.Event):
    """Atualiza os registos com valores aleatórios a cada 2 segundos.

    O loop termina quando ``stop_event`` é definido.
    """
    while not stop_event.is_set():
        temperatura = int(random.uniform(20.0, 80.0) * 10)
        pressao = int(random.uniform(1.0, 10.0) * 10)
        estado = random.choice([0, 1])
        store.setValues(3, 0, [temperatura, pressao, estado])
        log.info(
            "[Modbus Server] Temp: %.1f C | Pressao: %.1f bar | Estado: %s",
            temperatura / 10.0,
            pressao / 10.0,
            "A correr" if estado else "Parado",
        )
        stop_event.wait(2)

# -------------------------------------------------------------------
# Execução do servidor
# -------------------------------------------------------------------
def main():
    stop_event = threading.Event()
    def handle_signal(signum, frame):
        log.info("Sinal %s recebido, encerrando servidor...", signum)
        stop_event.set()
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    t = threading.Thread(target=simular_dados, args=(stop_event,), daemon=True)
    t.start()
    log.info("=" * 50)
    log.info("Servidor Modbus TCP a correr em %s:%s", MODBUS_HOST, MODBUS_PORT)
    log.info("=" * 50)
    try:
        StartTcpServer(context=context, address=(MODBUS_HOST, MODBUS_PORT))
    except Exception as exc:
        log.error("Erro ao iniciar o servidor Modbus: %s", exc)
    finally:
        stop_event.set()
        t.join()
        log.info("Servidor Modbus encerrado.")

if __name__ == "__main__":
    main()
