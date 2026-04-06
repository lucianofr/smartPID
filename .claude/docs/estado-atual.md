# Estado Atual — OPC-UA Server Independent Control

**Data:** 2026-04-06
**Branch:** `feat/opcua-server-independent` (10 commits ahead of main)

## Implementado
- Porta default do simulador OPC-UA corrigida de 4841 → 4849
- Lifecycle do OPC-UA server desacoplado do loop de simulacao
- 3 novos endpoints REST: GET/POST /simulator/opcua/{status,start,stop}
- SimulatorPage com indicador de status OPC-UA + botoes Start/Stop independentes
- 112 testes passando, lint limpo

## Proximos passos
- Merge para main (aguardando aprovacao do usuario)
- Stash pendente em feat/project-upload-download (stash@{0})
