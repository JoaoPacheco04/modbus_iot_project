import os
import random
import threading
import time
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)

# -------------------------------------------------------------------
# Holding Registers iniciais (indice 0, 1, 2):
#   0 -> temperatura  (valor x 10, ex: 253 = 25.3 C)
#   1 -> pressao      (valor x 10, ex: 42  = 4.2 bar)
#   2 -> estado maquina (0 = parado, 1 = a correr)
# -------------------------------------------------------------------
MODBUS_HOST = os.getenv("MODBUS_HOST", "0.0.0.0")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))

store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [250, 42, 1])
)
context = ModbusServerContext(slaves=store, single=True)


def simular_dados():
    """Atualiza os registos com valores aleatorios a cada 2 segundos."""
    while True:
        temperatura = int(random.uniform(20.0, 80.0) * 10)
        pressao = int(random.uniform(1.0, 10.0) * 10)
        estado = random.choice([0, 1])

        store.setValues(3, 0, [temperatura, pressao, estado])

        print(
            f"[Modbus Server] "
            f"Temp: {temperatura / 10:.1f} C | "
            f"Pressao: {pressao / 10:.1f} bar | "
            f"Estado: {'A correr' if estado else 'Parado'}"
        )
        time.sleep(2)


# Corre a simulação numa thread separada
t = threading.Thread(target=simular_dados, daemon=True)
t.start()

print("=" * 50)
print(f" Servidor Modbus TCP a correr em {MODBUS_HOST}:{MODBUS_PORT}")
print("=" * 50)
StartTcpServer(context=context, address=(MODBUS_HOST, MODBUS_PORT))
