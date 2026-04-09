# Projeto IoT — Modbus + EdgeX + MQTT + InfluxDB

Simulação de um ambiente industrial com leitura de sensores via Modbus TCP, integração com a plataforma EdgeX Foundry, transporte de dados por MQTT e persistência em InfluxDB.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│  Parte 1 — Simulação Modbus                                     │
│  modbus-server (server.py) — porta 1502                         │
│  Simula: temperatura, pressão, estado da máquina                │
└────────────────────┬────────────────────────────────────────────┘
                     │ Modbus TCP
          ┌──────────┴──────────┐
          │                     │
┌─────────▼──────────┐  ┌──────▼──────────────────────────────┐
│  Parte 2 — Python  │  │  Parte 2 — EdgeX Foundry             │
│  modbus-client     │  │  device-modbus → core-data           │
│  (client.py)       │  │  → app-service-mqtt-export           │
└─────────┬──────────┘  └──────┬──────────────────────────────┘
          │ MQTT                │ MQTT
          │ modbus/factory/     │ edgex/factory/sensors
          │ sensors             │
          └──────────┬──────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  Parte 3 — Persistência                                          │
│  mosquitto (porta 1884) → influxdb-export (subscriber.py)       │
│  → InfluxDB (porta 8086)                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pré-requisitos

- Docker Engine 24+
- Docker Compose v2.20+

---

## Arranque rápido

```bash
# 1. Clonar o repositório
git clone <url-do-repositório>
cd <pasta-do-projeto>

# 2. Criar o ficheiro de variáveis de ambiente
cp .env.example .env
# Editar .env se necessário (valores padrão já funcionam para desenvolvimento)

# 3. Arrancar todos os serviços
docker compose up -d

# 4. Verificar que todos os serviços estão saudáveis
docker compose ps
```

O arranque completo demora cerca de **60 segundos** devido às dependências do EdgeX.

---

## Verificar o funcionamento

### Logs do fluxo principal (EdgeX)
```bash
docker logs -f edgex-device-modbus
docker logs -f influxdb-export
```

### Logs do fluxo secundário (Python)
```bash
docker logs -f modbus-client
```

### Aceder ao InfluxDB
Abrir `http://localhost:8086` no browser.

- Utilizador: `admin`
- Password: definida no `.env` (padrão: `password123`)
- Organização: `edgex-org`
- Bucket: `factory`

Query de exemplo (Flux):
```flux
from(bucket: "factory")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "factory_sensors")
  |> filter(fn: (r) => r._field == "temperature")
```

---

## Estrutura do projeto

```
.
├── modbus-server/
│   └── server.py              # Servidor Modbus TCP simulado
├── modbus-client/
│   └── client.py              # Cliente Modbus → MQTT (Python)
├── influx/
│   ├── subscriber.py          # Subscriber MQTT → InfluxDB
│   └── configuration.yaml     # Configuração alternativa via ficheiro
├── mqtt/
│   ├── profiles/              # Perfil EdgeX do dispositivo Modbus
│   └── devices/               # Definição do dispositivo EdgeX
├── mosquitto/
│   └── mosquitto.conf         # Configuração do broker MQTT externo
├── Dockerfile.python-app      # Imagem base para os scripts Python
├── docker-compose.yml         # Orquestração de todos os serviços
├── .env.example               # Template das variáveis de ambiente
└── requirements.txt           # Dependências Python
```

---

## Tópicos MQTT

| Tópico                      | Produtor            | Consumidor          | Formato  |
|-----------------------------|---------------------|---------------------|----------|
| `modbus/factory/sensors`    | modbus-client       | influxdb-export     | Simples  |
| `edgex/factory/sensors`     | app-service (EdgeX) | influxdb-export     | EdgeX    |

### Formato simples (modbus-client Python)
```json
{
  "temperature": 25.3,
  "pressure": 4.1,
  "machine_state": 1,
  "timestamp": 1712600000
}
```

### Formato EdgeX (app-service)
```json
{
  "deviceName": "modbus-factory-device",
  "origin": 1712600000000000000,
  "readings": [
    {"resourceName": "temperature",   "value": "25.3"},
    {"resourceName": "pressure",      "value": "4.1"},
    {"resourceName": "machine_state", "value": "1"}
  ]
}
```

---

## Parar o projeto

```bash
# Parar todos os serviços
docker compose down

# Parar e remover volumes (apaga dados do InfluxDB e PostgreSQL)
docker compose down -v
```