## Demo Rapida

### Como arrancar

```powershell
docker compose up -d --build
```

### O que mostrar

1. Confirmar que o servidor Modbus esta a simular dados:

```powershell
docker compose logs --tail=20 modbus-server
```

2. Confirmar que o cliente Python le Modbus e publica em MQTT:

```powershell
docker compose logs --tail=20 modbus-client
```

3. Confirmar que o exportador grava no InfluxDB:

```powershell
docker compose logs --tail=20 influxdb-export
```

4. Abrir o InfluxDB:

- URL: `http://localhost:8086`
- org: `edgex-org`
- bucket: `factory`
- token: `edgex-influx-token-2024`

5. Confirmar EdgeX:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:59881/api/v3/device/all
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:59880/api/v3/event/device/name/modbus-factory-device
```

### Frase curta para explicar

O projeto usa um servidor Modbus TCP simulado, um cliente Python que le os registos, publica em MQTT, persiste no InfluxDB e integra o mesmo dispositivo no EdgeX atraves do `device-modbus`.
