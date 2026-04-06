# Estado Atual — Expor variáveis do simulador via OPC-UA

**Data:** 2026-04-06
**Branch:** `fix/opcua-expose-simulator-variables`

## Implementado
- Address space OPC-UA reorganizado com sub-pastas por controlador:
  - `CTRL_{id}/PID/` — PV, SP, CO, Mode, Status, Kp, Ti, Td, PID_Mode, PID_SP, PID_Enabled, PID_CV, Error
  - `CTRL_{id}/Process/` — Gain, Tau1, Tau2, DeadTime, Preset, PV_Min, PV_Max, Input, Output
  - `CTRL_{id}/Disturbance/` — Step_Active, Step_Amplitude, Noise_Active, Noise_Amplitude, Auto_SP_Enabled/Min/Max, Auto_Dist_Enabled/Max
- API `update_values()` simplificada para receber `values: dict` em vez de parâmetros individuais
- Simulator `_tick()` agora publica todas as 31 variáveis a cada ciclo
- 64 testes passando (unit + integration OPC-UA), lint limpo

## Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- `tests/core/unit/test_opcua_server.py`
- `tests/core/unit/test_simulator_adapter.py`
- `tests/core/integration/test_opcua_fullstack.py`

## Próximos passos
- Aguardar aprovação do usuário para commit e merge
