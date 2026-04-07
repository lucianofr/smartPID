# Estado Atual — Fix Settings OPC-UA Connect/Disconnect

**Data:** 2026-04-06
**Branch:** `fix/settings-opcua-connect-disconnect`

## O que foi feito

### Settings Page — botões Connect/Disconnect
- Substituído botão "Reconnect" por "Connect" e "Disconnect" separados
- Estado inicial: Connect habilitado, Disconnect desabilitado
- Ao conectar: mostra "Connecting..." (amarelo), depois "Connected" (verde) ou "Disconnected" (vermelho)
- Botões se habilitam/desabilitam conforme estado da conexão

### Backend — endpoint disconnect
- Adicionado `POST /opcua/disconnect` no router OPC-UA
- `POST /opcua/connect` agora retorna `OPCUAStatusResponse` com estado real (espera até 5s)

### HMI — auto-reconnect watchdog
- Timer QTimer de 5s (`_opcua_watchdog`) monitora conexão OPC-UA após primeiro connect
- Se detecta queda: tenta reconectar automaticamente via `POST /opcua/connect`
- Usa signal thread-safe `_opcua_status_signal` para atualizar UI

### API Client + Ports + Mock
- Adicionados métodos: `opcua_client_status()`, `opcua_client_connect()`, `opcua_client_disconnect()`
- Atualizados `APIClientPort` (ports.py) e `MockAPIClient` (mock_service.py)

## Verificação: OPC-UA client thread
O `OPCUAAdapter` (backend) já executa em thread independente (`daemon=True`, nome "opcua-client") com event loop asyncio dedicado. O watchdog interno lê `ServerStatus_State` a cada 5s e reconecta com backoff exponencial.

## Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`
- `tests/hmi/pages/test_settings_page.py`
- `tests/hmi/test_settings_apply_cancel.py`

## Testes: 33 passed (settings + apply/cancel)

## Próximos passos
- Aguardar revisão/merge pelo usuário
