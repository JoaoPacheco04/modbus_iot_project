# Demo Quickstart (Modbus + EdgeX + MQTT + InfluxDB)

## Architecture
```
Part 1 (Modbus server)
modbus-server (TCP/1502)
        |
        v
Part 2 (EdgeX flow - main)
device-modbus -> core-data -> app-service-mqtt-export
        |
        v
MQTT (external broker)
edgex-mosquitto:1884  topic: edgex/factory/sensors
        |
        v
influxdb-export -> InfluxDB

Part 2 (Python client - demo)
modbus-client -> reads Modbus only (no MQTT)
```

## Start (clean)
```powershell
docker compose down

docker compose up -d database mqtt-broker core-keeper core-common-config-bootstrapper
docker compose up -d core-metadata core-data core-command
docker compose up -d modbus-server device-modbus app-service-mqtt-export
docker compose up -d mosquitto influxdb influxdb-export
```

## Optional: Part 2 (Python Modbus client)
```powershell
docker compose start modbus-client
docker compose logs --tail=10 modbus-client
docker compose stop modbus-client
```

## Verify (EdgeX flow)
```powershell
docker compose ps
docker compose logs --tail=10 device-modbus
docker compose logs --tail=10 influxdb-export
```

## MQTT proof (EdgeX topic)
```powershell
docker compose exec mosquitto mosquitto_sub -h edgex-mosquitto -p 1884 -t edgex/factory/sensors -v
```

## InfluxDB query (proof of persistence)
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8086/api/v2/query?org=edgex-org" `
  -Headers @{ Authorization = "Token edgex-influx-token-2024"; Accept="application/csv"; "Content-Type"="application/vnd.flux" } `
  -Body 'from(bucket: "factory") |> range(start: -5m) |> limit(n: 10)'
```

## Stop
```powershell
docker compose down
```
