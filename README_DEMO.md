# Projeto IoT — Modbus + EdgeX + MQTT + InfluxDB

## Arquitetura

```
                        PARTE 1 (Servidor Modbus)
                    ┌── modbus-server (TCP/1502) ──┐
                    │                               │
            PARTE 2 (EdgeX)                  PARTE 2+3 (Python)
                    │                               │
            device-modbus                    modbus-client
                    │                               │
              core-data                             │
                    │                               │
         app-service-export                    MQTT publish
                    │                               │
                    v                               v
              mosquitto (porta 1884)          mosquitto (1884)
        topic: edgex/factory/sensors    topic: modbus/factory/sensors
                    │                               │
                    └───────────┬───────────────────┘
                                v
                     influxdb-export (subscriber.py)
                                │
                                v
                            InfluxDB
```

## Componentes EdgeX Usados

| Serviço | Imagem | Função |
|---|---|---|
| **database** | postgres:16.3 | Base de dados do EdgeX |
| **mqtt-broker** | eclipse-mosquitto | Message Bus interno EdgeX |
| **core-keeper** | edgexfoundry/core-keeper:4.0.0 | Registo e configuração de serviços |
| **core-common-config** | edgexfoundry/core-common-config-bootstrapper:4.0.0 | Bootstrap de configuração partilhada |
| **core-metadata** | edgexfoundry/core-metadata:4.0.0 | Gestão de dispositivos e perfis |
| **core-data** | edgexfoundry/core-data:4.0.0 | Receção e armazenamento de eventos |
| **core-command** | edgexfoundry/core-command:4.0.0 | Interface de comandos para dispositivos |
| **device-modbus** | edgexfoundry/device-modbus:4.0.0 | Leitura Modbus TCP → Eventos EdgeX |
| **app-service-mqtt-export** | edgexfoundry/app-service-configurable:4.0.0 | Exporta eventos para MQTT externo |

## Arranque

```powershell
# 1) Parar tudo (se necessário)
docker compose down

# 2) Infraestrutura base EdgeX
docker compose up -d database mqtt-broker core-keeper core-common-config-bootstrapper

# 3) Core services EdgeX (esperar ~10s)
docker compose up -d core-metadata core-data core-command

# 4) Modbus + Device Service + Export
docker compose up -d modbus-server device-modbus mosquitto app-service-mqtt-export

# 5) InfluxDB + Subscriber + Cliente Python
docker compose up -d influxdb influxdb-export modbus-client
```

## Verificação

### Todos os serviços a correr
```powershell
docker compose ps
```

### Dados EdgeX a fluir
```powershell
docker compose logs --tail=10 device-modbus
docker compose logs --tail=10 influxdb-export
```

### Dados Python a fluir
```powershell
docker compose logs --tail=10 modbus-client
```

### MQTT — ver dados em tempo real
```powershell
# Dados EdgeX
docker compose exec mosquitto mosquitto_sub -h edgex-mosquitto -p 1884 -t "edgex/factory/sensors" -v

# Dados Python client
docker compose exec mosquitto mosquitto_sub -h edgex-mosquitto -p 1884 -t "modbus/factory/sensors" -v
```

### InfluxDB — consultar dados persistidos
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8086/api/v2/query?org=edgex-org" `
  -Headers @{ Authorization = "Token edgex-influx-token-2024"; Accept="application/csv"; "Content-Type"="application/vnd.flux" } `
  -Body 'from(bucket: "factory") |> range(start: -5m) |> limit(n: 10)'
```

## Parar
```powershell
docker compose down
```
