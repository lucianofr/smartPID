# Plano de execução — Malha SUPERVISORY somente-leitura e sintonia manual no faceplate

**Documento:** Plano de execução

**Design:** docs/refactor-supervisory.md (23 decisões fechadas, D1–D23; glossário em `CONTEXT.md`; ADR em `docs/adr/0001-escrita-manual-de-sintonia-sem-limites.md`)

**Data:** 2026-08-07

**Baseline:** HEAD `b3a2431` (todos os anchors abaixo conferidos nesse commit). Números de linha são desse commit — reler cada região antes de editar.

**Execução:** pipeline `orch-change-feature` (motor `orch-pipeline`), size **large**: fases 0 → 2 (leve) → 4 → 5 → 6. Fase 4 (TDD): em cada fatia, atualizar primeiro os testes para o novo contrato, depois a implementação até verde. Fase 5 (review): `code-reviewer` + `python-reviewer` (fatias 2–3) / `react-reviewer` (fatia 4), com `security-reviewer` nas fatias 2–3 (autorização de rotas de comando). Um commit por fatia (mensagens inline). A fatia 1 roda primeiro e sozinha (D22).

Uma malha SUPERVISORY passa a recusar `POST /commands/setpoint|mode|output` com 409 no backend; o faceplate dela perde entradas de SP/CO e botões AUTO/MAN (MODE vira badge); caixas Kp/Ti/Td entram no faceplate **nos dois modos**, aplicando com ENTER via `POST /commands/tuning` — que perde os clamps do otimizador, ganha 422 para `Kp < KP_MIN` e ganha ramo DDC (persiste `pid_params`); badges SUPERVISORY/DDC no faceplate e no card de malha.

## Fatia 1 — fixtures explícitos (não muda comportamento)

O harness e2e **não roda backend** (`harness.ts:4` — REST/WS mockados), então `execution_mode` em fixture e2e é dado inerte até a fatia 4; no backend, só 2 fixtures dependem do default implícito do dataclass. Tudo abaixo é neutro em comportamento.

### 1a. `harness.ts`

- `interface HarnessLoop` (`:18-29`): novo campo **obrigatório** `executionMode: 'SUPERVISORY' | 'DDC';` (camelCase como `euMin`; obrigatório para o TS forçar todo fixture a declarar — D22). Literais com spread (`{ ...FIC101, mode: 'MAN' }` em `target-size.spec.ts:10` e `user-role.spec.ts:~97`) herdam e seguem compilando.
- `FIC101` (`:31-42`): `executionMode: 'SUPERVISORY'` (D23 — honra o comentário de `integral-type.spec.ts:9-12`).
- `TIC202` (`:44-55`): `executionMode: 'DDC'`.
- `controllerPayload()` (`:57-85`): adicionar `execution_mode: loop.executionMode,` ao objeto retornado.

### 1b. `fatia2-commands.spec.ts`

O payload de PIC-005 é um literal próprio (`:13-26`, não usa `controllerPayload`): adicionar `execution_mode: 'DDC',` (D23 — o spec existe para exercitar comandos).

### 1c. `test_api_commands.py`

- `_create_and_start_controller` (`:21-29`): no `Controller(...)` default (`:27-29`), adicionar `execution_mode=ExecutionMode.SUPERVISORY` (torna explícito o default de `controller.py:168`). `ExecutionMode` já está importado no arquivo (usado em `:57` etc.).
- `test_output_above_limit_rejected_in_monitor_mode` (`:445-474`): no Controller FIC-403 (`:456-460`), adicionar `execution_mode=ExecutionMode.DDC`. Neutro (o override de daemon `monitor` em `:464` decide a rota) e torna o teste a prova explícita da ordem daemon→malha da §5.2 do design.
- Todos os demais Controllers do arquivo **já são explícitos** (verificado: TIC-400/401/402, FIC-500/501, TIC-600–603, TIC-700–703, FIC-800–803, `_create_and_start_ddc_controller`).

**Commit:** `test: pin execution_mode explicitly in e2e and integration fixtures`

## Fatia 2 — backend: recusa de SP/CO/MODE em SUPERVISORY

### 2a. `commands.py` — produção

1. Após `_MONITOR_DETAIL` (`:55`), nova constante (literal exato da §5.1 do design, pt-BR — é contrato de UI):

```python
_SUPERVISORY_DETAIL = (
    "Malha em SUPERVISORY: PV/SP/CO/MODE são somente leitura. "
    "O DCS é o dono desta malha."
)
```

2. `_dcs_owns_loop` (`:58-81`) encolhe para o eixo do daemon (D4/D5 — a função permanece, o ramo da malha sai). Parâmetros `lm`/`controller_id` ficam mortos → cutover limpo na assinatura; docstring reescrito:

```python
def _dcs_owns_loop(execution_mode: str) -> bool:
    """True when the whole daemon runs in monitor mode: every SP/CO/mode
    command is then written to the DCS over OPC-UA instead of the internal
    PIDWorker. The per-loop axis (SUPERVISORY) no longer routes here — it
    refuses outright, see ``_refuse_supervisory``."""
    return execution_mode == "monitor"
```

Callsites a ajustar (exatamente 3): `:121`, `:160`, `:197` → `_dcs_owns_loop(execution_mode)`.

3. Novo helper logo abaixo (nenhum equivalente existente; `ControllerNotFoundError` e `ExecutionMode` já importados):

```python
def _refuse_supervisory(lm: LoopManager, controller_id: int) -> None:
    """409 for a process-variable command on a SUPERVISORY loop.

    Runs only on the local branch, i.e. daemon in execute mode — the daemon
    axis is checked first (design §5.2). Unknown controller falls through:
    the local branch right after answers its own 404.
    """
    try:
        ctrl = lm.get_controller(controller_id)
    except ControllerNotFoundError:
        return
    if ctrl.execution_mode is ExecutionMode.SUPERVISORY:
        raise HTTPException(status_code=409, detail=_SUPERVISORY_DETAIL)
```

4. Nas três rotas, o `else:` (ramo local) ganha a recusa como primeira linha — forma idêntica nas três:

- `set_setpoint` (`else:` em `:131-132`):
  ```python
  else:
      _refuse_supervisory(lm, body.controller_id)
      lm.set_setpoint(body.controller_id, body.value)
  ```
- `set_mode` (`else:` em `:168-169`): idem antes de `lm.set_mode(...)`.
- `set_output` (`else:` em `:223-224`): idem antes de `lm.set_output(...)`.

O ramo DCS (daemon `monitor`) fica **intocado**: `_write_to_dcs` (`:84-107`), span checks (`:129`, `:207`) e a guarda de MAN (`:215-221`) continuam vivos para malha DDC em daemon `monitor` (D5). Sem regen de OpenAPI nesta fatia (nenhum docstring/assinatura de rota muda).

### 2b. `test_api_commands.py` — atualizar antes da implementação (TDD)

Padrão para forçar daemon `monitor` num teste: o de `:452-472` (`app.dependency_overrides[get_execution_mode] = lambda: "monitor"` com `try/finally pop`). O app de teste roda em `execute` por default.

`TestDCSBranchHonoursLoopLimits` (`:353`) — docstring da classe reescrito (o ramo DCS agora é só daemon-monitor; SUPERVISORY em execute recusa antes de qualquer span):

| Teste (linha atual) | Mudança |
|---|---|
| `test_setpoint_above_limit_rejected_on_dcs_branch` (`:363`) | renomear `test_setpoint_on_supervisory_loop_refused_409`; esperar `409`, `resp.json()["detail"] == _SUPERVISORY_DETAIL` (importar a constante do router), `fake.params == []` |
| `test_setpoint_below_limit_rejected_on_dcs_branch` (`:390`) | **apagar** — após a mudança seria o mesmo contrato do teste acima (valor acima/abaixo do limite é indiferente: a recusa vem antes do span) |
| `test_setpoint_inside_limits_still_reaches_dcs` (`:417`) | renomear `test_setpoint_inside_limits_reaches_dcs_in_monitor_mode`; Controller ganha `execution_mode=ExecutionMode.DDC`, teste ganha o override de daemon `monitor`; mantém `200` + `fake.params == [(cid, "sp", 55.0)]` |
| **novo** `test_setpoint_above_limit_rejected_in_monitor_mode` | DDC + daemon `monitor` + `value=150.0` com `sp_hi_lim=100` → `400`, `fake.params == []`. Preserva a cobertura do span de SP no ramo DCS (espelho do teste de output `:445`), que os dois renames acima deixariam órfã |
| `test_output_above_limit_rejected_in_monitor_mode` (`:445`) | sem mudança além da fatia 1 (já DDC + monitor; continua `400`) |
| `test_output_reaches_dcs_on_supervisory_loop` (`:477`) | renomear `test_output_on_supervisory_loop_refused_409`; esperar `409` + detail `== _SUPERVISORY_DETAIL` + `fake.params == []`; docstring invertido (antes provava a escrita, agora prova a recusa) |
| `test_output_above_limit_rejected_on_supervisory_loop` (`:512`) | **apagar** — duplicaria o contrato do rename acima |

`TestSupervisoryWithoutLinkRefuses` (`:539-622`): os 3 asserts são `status_code == 409` puro (verificado `:574/:587/:600`) → **passam sem edição**; o 409 agora vem de `_refuse_supervisory` e não da checagem de adapter. Atualizar só o docstring da classe (a ausência de link deixou de ser o motivo da recusa em execute mode). `test_ddc_loop_still_handled_locally` (`:603`) fica como está.

`TestSupervisoryModeReachesTheDCS` (`:625-652`):
- `test_mode_written_over_opcua` (`:633`): reescrever como `test_mode_written_over_opcua_in_monitor_mode` — Controller TIC-700 ganha `execution_mode=ExecutionMode.DDC`, teste ganha override de daemon `monitor`; mantém `200` + `fake.modes == [(cid, ControllerMode.AUTO)]` (preserva a cobertura do write de MODE no ramo DCS).
- **novo** `test_mode_on_supervisory_loop_refused_409`: SUPERVISORY + execute + `_FakeOPCUA()` conectado → `409`, detail `== _SUPERVISORY_DETAIL`, `fake.modes == []` (prova que a recusa não é o caso "sem link").
- Renomear a classe para `TestMonitorModeReachesTheDCS` e ajustar o docstring.

`TestOutputWriteHardening` (`:771-867`): o helper `_loop` (`:777-786`) muda para `execution_mode=ExecutionMode.DDC`, e **cada um dos 4 testes** ganha o override de daemon `monitor` (padrão `:464`, try/finally). Expectativas atuais preservadas (`409` detail com `'co'`, `409` detail com `'AUTO'`, `200`+escrita, `200`+escrita) — é onde esses caminhos continuam vivos (§5.2). Docstring da classe: trocar "SUPERVISORY output" por "monitor-mode output".

**Commit:** `feat(api): refuse setpoint/mode/output on SUPERVISORY loops with 409`

## Fatia 3 — backend: sintonia manual sem trilhos + ramo DDC

### 3a. `commands.py` — produção

1. Imports: remover `clamp_tuning_change` do bloco `:33-37` (**manter** `clamp_tuning_absolute` e `clamp_tuning_params` — `apply_tuning` usa as duas, `:470` e `:483`). Adicionar `from smart_pid_domain.models.controller import KP_MIN`.
2. Nova constante junto de `_SUPERVISORY_DETAIL` (literal pt-BR — decisão registrada em Suposições):

```python
_KP_MIN_DETAIL = (
    f"Kp abaixo do mínimo físico ({KP_MIN:g}): zeraria a ação proporcional. "
    "Escrita recusada."
)
```

3. `write_tuning` (`:312-392`) reescrito por inteiro. Assinatura ganha `repo: Annotated[SQLiteRepository, Depends(get_repo)]` (ambos já importados). Corpo:

```python
    """Manual Kp/Ti/Td write, routed to whoever runs the PID.

    SUPERVISORY: written to the DCS block over OPC-UA; the database is not
    touched — the 1 Hz read-back stays the source of truth. DDC: persisted
    into ``pid_params`` and pushed to the live PIDWorker. The optimizer
    guardrails do not apply to this manual path (ADR 0001,
    docs/adr/0001-escrita-manual-de-sintonia-sem-limites.md); the one refusal
    is ``Kp < KP_MIN``, answered with 422 instead of a silent clamp.
    """
    controller_id = body.controller_id
    ctrl = lm.get_controller(controller_id)

    if body.kp is not None and body.kp < KP_MIN:
        raise HTTPException(status_code=422, detail=_KP_MIN_DETAIL)

    if ctrl.execution_mode is ExecutionMode.SUPERVISORY:
        opcua = getattr(request.app.state, "opcua_adapter", None)
        if opcua is None or not opcua.is_connected:
            raise HTTPException(status_code=409, detail="OPC-UA not connected")
        opcua.write_pid_params(controller_id, body.kp, body.ti, body.td)
    else:
        updates: dict[str, float] = {}
        if body.kp is not None:
            updates["gain"] = body.kp
        if body.ti is not None:
            updates["reset"] = body.ti
        if body.td is not None:
            updates["rate"] = body.td
        if updates:
            updated = replace(ctrl, pid_params=replace(ctrl.pid_params, **updates))
            await repo.save(updated)
            lm.update_controller(updated)
```

- O ramo DDC copia o par que `PUT /controllers/{id}` já faz (`controllers.py:549-564`: `replace` + `repo.save` + `loop_manager.update_controller`); `lm.update_controller` (`loop_manager.py:169-185`) propaga ao PIDWorker/AIWorker vivos e é no-op se a malha não está registrada. `replace` já está importado (`commands.py:6`).
- Campos ausentes (`None`) não são tocados (contrato do DTO, sem mudança de esquema — `TuningCommand` já é `kp/ti/td` opcionais). Corpo todo-`None` em DDC: no-op + 200 + auditoria "no change" (mesmo comportamento efetivo de hoje).
- Auditoria e resposta mantêm a forma atual, trocando as variáveis clampadas pelos valores do body: `json.dumps({"kp": body.kp, "ti": body.ti, "td": body.td})`, `_parts` sobre `(("Kp", body.kp), ("Ti", body.ti), ("Td", body.td))`, `detail=f"Tuning written: Kp={body.kp}, Ti={body.ti}, Td={body.td}"`. `require_admin` e `AuditAction.TUNE_PID` inalterados nos dois ramos (D6).
- `apply_tuning` (`:441-551`): **intocado**.

4. `dtos/commands.py:45-52` — docstring de `TuningCommand` está falso após a mudança; reescrever:

```python
    """Direct PID tuning write. A SUPERVISORY loop receives it on the DCS
    block over OPC-UA; a DDC loop persists it into ``pid_params``. Only the
    supplied fields are written; ``kp`` below ``KP_MIN`` is refused with 422
    (ADR 0001)."""
```

5. `packages/smart_pid_core/src/smart_pid_core/domain/services/tuning_guardrails.py` — o docstring de `clamp_tuning_absolute` (região `:31-75`, reler antes de editar) afirma que o clamp impede o caminho manual de contornar limites; essa frase agora descreve só o caminho da IA. Ajustar a frase citando `apply-tuning`/`io_worker` como únicos chamadores e referenciar `docs/adr/0001-...`. As 3 funções permanecem intactas.

6. Regenerar o contrato OpenAPI (docstrings embedam em `openapi.json:2919` e `:3974`): `cd packages/smart_pid_web && npm run gen:api` → commit inclui `openapi.json` + `src/api/generated/openapi.ts` (senão `gen:api:check` quebra no CI).

### 3b. `test_api_commands.py` — atualizar antes da implementação (TDD)

`TestWriteTuningCommand` (`:221`):

| Teste (linha atual) | Mudança |
|---|---|
| `test_out_of_range_params_clamped` (`:247`) | renomear `test_manual_write_is_not_clamped`: POST `kp=100.0` → `200`; `fake.written == (cid, 100.0, None, None)` (a tupla de `_FakeOPCUA.written` é `(id, kp, ti, td)`, ver unpack em `:693`) |
| `test_kp_floored_at_absolute_minimum` (`:285`) | renomear `test_kp_below_minimum_refused_422`: POST `kp=0.0` → `422`; `"Kp abaixo do mínimo físico" in resp.json()["detail"]`; `fake.written is None` |
| `test_supervisory_ti_raised_into_configured_band` (`:319`) | renomear `test_supervisory_ti_outside_ai_band_written_verbatim`: POST `ti=0.5` com banda 1,0–10,0 → `200`; ti escrito `== 0.5` (D7) |

`TestTuningClampsComposeByExecutionMode` (`:655`) — renomear `TestTuningWriteDispatchesByExecutionMode`, docstring novo (o despacho por modo é o contrato agora):

| Teste | Mudança |
|---|---|
| `test_ddc_loop_keeps_zero_ti_instead_of_the_ai_band` (`:664`) | reescrever como `test_ddc_write_persists_pid_params_and_skips_opcua`: mesmo setup (TIC-701 DDC, `reset=0.5`), POST `ti=0.0` → `200`; `fake.written is None`; `(await api_deps["repo"].get(cid)).pid_params.reset == 0.0` **e** `.gain == 1.0` (escrita parcial preserva os ausentes); `api_deps["loop_manager"].get_controller(cid).pid_params.reset == 0.0` (propagou ao loop vivo) |
| `test_absolute_clamp_still_fires_after_the_rate_clamp` (`:697`) | **apagar** — a composição de clamps não existe mais; o 422 já está coberto |
| `test_clamped_write_is_logged` (`:733`) | **apagar** — o log de clamp que ele defende foi removido junto com o clamp |
| **novo** `test_kp_below_minimum_refused_on_ddc_too` | malha DDC, POST `kp=0.0` → `422`; `(await api_deps["repo"].get(cid)).pid_params.gain == 1.0` (nada persistido — KP_MIN é invariante de domínio, vale nos dois ramos) |

Intocados e devem seguir verdes: `tests/core/unit/test_guardrails.py` inteiro, os testes de `TestApplyTuning`, `tests/domain/test_dtos_validation.py::test_all_fields_remain_optional`, `test_role_contract.py`.

**Commit:** `feat(api): route manual tuning by execution mode, drop optimizer rails (ADR 0001)`

## Fatia 4 — frontend: gating, badges e caixas Kp/Ti/Td

### 4a. Módulo compartilhado novo — `src/features/dashboard/modeChip.ts`

Nenhum módulo compartilhado equivalente existe; criar com o conteúdo migrado de `LoopCard.tsx:74-99` (mover o bloco de comentário junto):

```ts
export interface ChipPaint { text: string; tint: string; }
export const RUNNING_TINT = /* valor atual em LoopCard.tsx (região :74-91, reler) */;
export const MODE_CHIP: Record<string, ChipPaint> = {
  AUTO: { text: 'text-state-running', tint: RUNNING_TINT },
  CAS: { text: 'text-state-running', tint: RUNNING_TINT },
  MAN: { text: 'text-alarm-warn', tint: 'var(--alarm-warn-bg)' },
  UNKNOWN: { text: 'text-alarm-warn', tint: 'var(--alarm-warn-bg)' },
};
export const MODE_CHIP_FALLBACK: ChipPaint = { text: 'text-text-soft', tint: 'var(--surface-sunk)' };
export const CHIP = 'border-transparent px-2 py-0.5 text-xs font-bold tracking-wide';
export const UNKNOWN_MODE_TITLE = 'Mapeamento de modos não configurado';
export const EXEC_MODE_TITLE: Record<ExecutionMode, string> = {
  SUPERVISORY: 'SUPERVISORY: o PID roda no CLP/DCS e o SmartPID só monitora.',
  DDC: 'DDC: o PID roda dentro do SmartPID, que escreve a saída diretamente.',
};
```

- `UNKNOWN` entra com a **pintura** warn do chip MAN, mantendo `tone="neutral"` no `Badge` — NÃO usar `tone="warn"` do Badge: os tones de severidade carregam `badge-glow` e são reservados a alarme (comentário em `LoopCard.tsx:75-77` e `Badge.tsx:19-23`). É assim que D19 ("tom warn") se realiza no padrão existente.
- `EXEC_MODE_TITLE` é a prosa de `LoopConfigDialog.tsx:595` dividida por modo (D17; a fonte não muda).
- `ExecutionMode` importado de `@/features/loop-config/types` (`types.ts:34`).
- `LoopCard.tsx` passa a importar tudo isso de `./modeChip` e perde as consts locais (`:74-99`). Callsites internos: `:127` (`MODE_CHIP[mode] ?? MODE_CHIP_FALLBACK`) e `:209-224` (os dois Badges usam `CHIP`). Nenhum teste importa as consts (verificado — `const` privadas hoje).

### 4b. `LoopCard.tsx`

- Chip de modo (`:209-215`): adicionar `title={mode === 'UNKNOWN' ? UNKNOWN_MODE_TITLE : undefined}`.
- Terceiro badge na linha `:208-225`, após o chip de estratégia:

```tsx
<Badge
  tone="neutral"
  title={EXEC_MODE_TITLE[execMode]}
  className={cn(CHIP, 'text-text-soft')}
>
  {execMode}
</Badge>
```

com `const execMode = (controller.execution_mode as ExecutionMode | undefined) ?? 'SUPERVISORY';` no corpo (mesmo cast/fallback de `LoopConfigDialog.tsx:339` — D16).

### 4c. `Faceplate.tsx`

1. `FaceplateProps` (`:20-30`): `executionMode?: ExecutionMode;` (import type de `@/features/loop-config/types`). Destructuring com default: `executionMode = 'SUPERVISORY'` (D16 — ausente = travado).
2. No corpo: `const supervisory = executionMode === 'SUPERVISORY';` e `const canTune = useCan('tuning.edit');` (padrão de `AiPanel.tsx:147`; import de `@/auth/useCan`).
3. Header (`:164-181`): badge de modo de execução ao lado do ponto de link — envolver o `<span>` do dot num `<div className="flex shrink-0 items-center gap-1.5">` junto com:

```tsx
<Badge tone="neutral" title={EXEC_MODE_TITLE[executionMode]} className={cn(CHIP, 'text-text-soft')}>
  {executionMode}
</Badge>
```

4. Gating dos controles (§7.2, D21 — o gate fica aqui, `CardControls` não muda): o `<div>` `:213-230` (os dois `CardControls`) só monta quando `!supervisory`.
5. Bloco de modo (`:232-249`): manter o rótulo `Modo PID`; trocar o miolo por condicional — em `supervisory`, no lugar do `role="group"` + botões:

```tsx
<Badge
  tone="neutral"
  style={{ backgroundColor: modeChip.tint }}
  className={cn('numeric self-start', CHIP, modeChip.text)}
  title={mode === 'UNKNOWN' ? UNKNOWN_MODE_TITLE : undefined}
>
  {mode}
</Badge>
```

com `const modeChip = MODE_CHIP[mode] ?? MODE_CHIP_FALLBACK;`. `mode` (`:114`) já vem decodificado do servidor — não mapear inteiro. Em DDC, os botões ficam como estão (`modeCmd`, `coDraft`/`coTouched` permanecem — só têm uso em DDC, e hooks não podem ser condicionais).
6. Caixas Kp/Ti/Td (§7.4, D11/D13/D14/D15/D20) — a linha de ganhos (`:139-143` e `:253-263`):
   - `interface Metric`/`gains` ganham `field: 'kp' | 'ti' | 'td'` por item (tipar `gains` localmente; `metrics()` de stats não muda).
   - Estado + mutação:

```tsx
const [tuningDrafts, setTuningDrafts] = useState<Record<'kp' | 'ti' | 'td', string>>({ kp: '', ti: '', td: '' });
const tuningCmd = useWriteTuningMutation();
const submitTuning = (field: 'kp' | 'ti' | 'td'): void => {
  const raw = tuningDrafts[field].trim();
  const value = Number(raw);
  if (raw === '' || !Number.isFinite(value) || tuningCmd.isPending) return;
  tuningCmd.mutate(
    { id: controllerId, [field]: value },
    {
      onSuccess: () => setTuningDrafts((d) => ({ ...d, [field]: '' })),
      onError: onCommandError,
    },
  );
};
```

   - Dentro do map da linha de ganhos, sob o valor, quando `canTune` (**nos dois modos** — D11):

```tsx
<Input
  aria-label={`Escrever ${gain.label}`}
  type="number"
  inputMode="decimal"
  className={TUNING_INPUT}
  placeholder={gain.value}
  value={tuningDrafts[gain.field]}
  onChange={(e) => setTuningDrafts((d) => ({ ...d, [gain.field]: e.target.value }))}
  onKeyDown={(e) => { if (e.key === 'Enter') submitTuning(gain.field); }}
/>
```

   com `const TUNING_INPUT = 'numeric mt-0.5 w-full min-w-0 px-1.5 py-1 text-right text-sm';` (const local nova; não exportar o `ENTRY_INPUT` privado de `CardControls.tsx:52` — D21). `Input` de `@/components/Field`. Uma caixa por coluna, sem linhas rótulo+campo (D20 — altura a 768 px, ver `SHORT_VIEWPORT` `:35-48`).
   - Comportamento fechado: repouso = campo vazio com valor vivo no `placeholder` (`gain.value` já é o formatado do read-back; `'—'` quando null); ENTER envia **só o campo editado**; sucesso limpa o campo (a confirmação visual é o placeholder acompanhar o read-back); erro (409/422/502) = toast `onCommandError` (`:129-131`) e campo preservado; ENTER com draft vazio/não-numérico/mutação pendente = no-op. Sem tratamento de Escape/blur (nada aplica sem ENTER).

### 4d. Camada de API

- `src/api/endpoints.ts` (objeto `endpoints`, junto de `setSetpoint` `:123`): adicionar

```ts
writeTuning: (controllerId: number, params: { kp?: number; ti?: number; td?: number }) =>
  api.post<CommandResponse>('/commands/tuning', { controller_id: controllerId, ...params }),
```

  Campos ausentes são omitidos do JSON (o DTO backend default a `None`).
- `src/features/loop-config/commandApi.ts:44-45`: trocar por delegação ao seam de spy (o padrão declarado no próprio arquivo, `:6-9`):

```ts
export interface TuningWrite { kp?: number; ti?: number; td?: number; }
export const writeTuning = (controllerId: number, params: TuningWrite) =>
  endpoints.writeTuning(controllerId, params);
```

- `src/features/loop-config/useCommands.ts:79-90`: `useWriteTuningMutation` vira

```ts
export function useWriteTuningMutation(): UseMutationResult<CommandResponse, ApiError, { id: number } & TuningWrite> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, ...params }: { id: number } & TuningWrite) => writeTuning(id, params),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}
```

  Callsites do par antigo: **nenhum** (código morto sendo conectado agora; verificado por grep — só definição e import em `useCommands.ts`). Cutover limpo, sem alias.

### 4e. `DashboardPage.tsx`

No mount do `Faceplate` (`:177-184`), adicionar `executionMode={selected.execution_mode as ExecutionMode | undefined}` (cast idêntico a `LoopConfigDialog.tsx:339`; import type de `@/features/loop-config/types`).

### 4f. Testes unitários

`Faceplate.test.tsx`:
- `renderFaceplate` (`:18-38`): assinatura `renderFaceplate(role: Role = 'admin', coScale?: Scale, executionMode: ExecutionMode | null = 'DDC')`, e no JSX `executionMode={executionMode ?? undefined}`. `null` = prop ausente (testa o default D16); **não** usar `undefined` como sentinela — parâmetro default do JS reativaria o `'DDC'`. Com o default `'DDC'` no helper, os 8 testes que tocam SP/CO/AUTO/MAN (`:91, :130, :140, :150, :157, :165, :186, :199`) passam **sem edição de corpo**; os 3 que só olham barras/wrapper (`:50, :55, :70`) idem.
- Novo `describe('Faceplate — SUPERVISORY')`:
  1. prop ausente = travado (D16): `renderFaceplate('user', undefined, null)` → sem `getByLabelText('Setpoint')`, sem botões `AUTO`/`MAN`/`Set setpoint`/`Set output` (`queryBy* → null`), badge `SUPERVISORY` visível.
  2. badge de modo no lugar do grupo: `renderFaceplate('admin', undefined, 'SUPERVISORY')` + `statusEnvelope(5, 1, { mode: 'AUTO' })` → `queryByRole('group', { name: 'Modo do controlador' })` null; `AUTO` visível via `{ selector: 'span.numeric' }`.
  3. UNKNOWN: `statusEnvelope(5, 1, { mode: 'UNKNOWN' })` → badge `UNKNOWN` com `title` `'Mapeamento de modos não configurado'`.
  4. caixas com permissão + ENTER envia só o campo: spy `vi.spyOn(endpoints, 'writeTuning').mockResolvedValue({ ok: true })` (mesmo seam de `:151/:158`); admin SUPERVISORY; `statusEnvelope` com `kp: 2` → `getByLabelText('Escrever Kp')` com `placeholder '2.00'`; digitar `2.2` + `fireEvent.keyDown(input, { key: 'Enter' })` → `writeTuning` chamado com `(5, { kp: 2.2 })`; campo limpo após sucesso.
  5. sem permissão: `renderFaceplate('user', undefined, 'SUPERVISORY')` → `queryByLabelText('Escrever Kp')` null (D15).
  6. D11: `renderFaceplate('admin')` (DDC) → caixas `Escrever Kp/Ti/Td` presentes **e** botões AUTO/MAN presentes.
  7. erro preserva o draft: spy rejeita → toast `Comando recusado` visível, input mantém `2.2`.

`LoopCard.test.tsx`: +1 teste — `makeController()` (fixture já é `execution_mode: 'SUPERVISORY'`, `fixtures.ts:38`) → badge `SUPERVISORY` visível; `makeController({ execution_mode: 'DDC' })` → `DDC`. Os 13 existentes não mudam (nenhum conta badges; verificado).

### 4g. Specs e2e

Migração dos specs que dirigem SP/CO/MODE de FIC-101 (agora SUPERVISORY) para TIC-202 (DDC), + casos novos de ausência (§10.3 do design):

- `faceplate.spec.ts`:
  - `:9` — trocar o assert do `group` (`:15`) por: badge `SUPERVISORY` visível no header; `fp.locator('span.numeric', { hasText: /^AUTO$/ })` visível (badge de modo); `fp.getByRole('group', { name: 'Modo do controlador' })` → `toHaveCount(0)`. Meters e stats ficam.
  - `:23` — reescrever: em FIC-101 com `role: 'user'`, `AUTO`/`MAN`/`Set setpoint`/`Set output`/`Setpoint` → `toHaveCount(0)`; `Escrever Kp` → `toHaveCount(0)` (user sem `tuning.edit`). Novo teste irmão: `role: 'admin'` em FIC-101 → `getByLabel('Escrever Kp')` visível e `Set setpoint` → `toHaveCount(0)`. Novo teste irmão: `gotoDashboard(page, { loops: [TIC202], role: 'user' })` → os cinco asserts de presença atuais (`:28-32`) movidos para `faceplate(page, 'TIC-202')`.
  - `:36` — sem mudança (Apply tuning é o AiPanel, fica nos dois modos).
  - `:41` — `gotoDashboard(page, { loops: [TIC202] })`, click em `faceplate(page, 'TIC-202')`, assert `{ controller_id: TIC202.id, mode: 'MAN' }`.
  - `:53` — `loops: [TIC202]` + `faceplate(page, 'TIC-202')`.
  - `:61` — baseline regravada (rail novo: badges + caixas, sem entradas SP/CO).
- `user-role.spec.ts`: `:8`, `:19` (o assert-precondição `:21`), `:53`, `:94` (usar `{ ...TIC202, mode: 'MAN' }`), `:123` → `loops: [TIC202]`; ids nos asserts de body `:104/:111/:120/:136`: `controller_id` 1 → 2. Novo teste: user no default FIC-101 → spinbutton `Setpoint`, botões `AUTO`/`MAN` e `Escrever Kp` → `toHaveCount(0)`; badge `SUPERVISORY` visível. `:32/:44/:139/:158` não mudam.
- `responsive.spec.ts` `:214` e `:231`: após o `gotoDashboard`, selecionar TIC-202 — `await loopCard(page, 'TIC-202').getByRole('button', { name: 'TIC-202', exact: true }).click();` — e trocar `faceplate(page, 'FIC-101')` por `'TIC-202'` **só nesses dois testes** (os demais medem layout e ficam em FIC-101).
- `target-size.spec.ts`: `MAN_LOOP = { ...TIC202, mode: 'MAN' }` (`:10`) e as referências `'FIC-101'` do arquivo (`:24-25`, `:33`) → `'TIC-202'`.
- `themes.spec.ts`: só regravar as 24 baselines (`:162-167`).
- `fatia2-commands.spec.ts` e `integral-type.spec.ts`: nada (PIC-005 já é DDC desde a fatia 1; integral-type só usa o dialog de configuração).

Regravação de screenshots (depois de todo o resto verde): `cd packages/smart_pid_web && npx playwright test faceplate.spec.ts themes.spec.ts --update-snapshots`, conferindo visualmente 2–3 PNGs (badge no header, caixas sob os ganhos, ausência das entradas SP/CO).

**Commit:** `feat(web): supervisory read-only faceplate with execution badges and tuning entry`

## Verificação

Comandos (raiz do repo, salvo indicação; backend usa a venv do workspace `uv`):

| Fatia | Prova |
|---|---|
| 1 | `uv run pytest tests/core/integration/test_api_commands.py -q` verde sem mudança de contagem; `cd packages/smart_pid_web && npm run typecheck && npm run test:e2e` verdes (fixtures inertes) |
| 2 | `uv run pytest tests/core/integration/test_api_commands.py -q` — os renomeados/novos passam; **prova do comportamento novo:** `test_setpoint_on_supervisory_loop_refused_409` (POST setpoint válido numa malha SUPERVISORY com adapter conectado → 409 com `_SUPERVISORY_DETAIL` e `fake.params == []`) e FIC-403 (DDC + daemon monitor) continua 400 — a ordem daemon→malha |
| 3 | idem; **prova:** `test_manual_write_is_not_clamped` (kp=100 chega como 100 ao DCS), `test_kp_below_minimum_refused_422`, `test_ddc_write_persists_pid_params_and_skips_opcua` (reset persiste 0.0, gain intacto, OPC não tocado); `tests/core/unit/test_guardrails.py` intacto e verde; `npm run gen:api && npm run gen:api:check` limpo |
| 4 | `cd packages/smart_pid_web && npm run test` (unit: os 7 novos + 8 legados sem edição de corpo) e `npm run test:e2e`; **prova:** o novo teste unitário 4 — digitar `2.2` em `Escrever Kp` + ENTER dispara `writeTuning(5, { kp: 2.2 })` e limpa o campo — e o spec novo de FIC-101 sem controles |
| final | suíte completa: `uv run pytest tests/ -q` · `npm run test && npm run typecheck && npm run lint && npm run test:e2e` (em `packages/smart_pid_web`) · `uv run ruff check .` |

E2E requer os browsers do Playwright já instalados (o repo já roda `test:e2e` hoje; nada novo a instalar).

## Suposições e contingências

- **Literal do 422** (`_KP_MIN_DETAIL`) é pt-BR para casar com `_SUPERVISORY_DETAIL` (o design fixou só o do 409). Se preferirem inglês (padrão dos details antigos), trocar o literal e o `in resp.json()["detail"]` do teste — nada mais depende dele.
- **Consolidação de testes**: 4 testes cujo contrato pós-mudança duplicaria outro foram apagados (`:390`, `:512`, `:697`, `:733`) e 4 adicionados (span de SP em monitor, MODE 409 com link vivo, 422 em DDC, persistência parcial DDC). A tabela §10.1 do design descreve impacto, não prescreve manutenção 1:1.
- **`docs/superpowers/plans/`** como destino do plano versionado (convenção dominante, 50 planos; `plans/NNN-*.md` descartada por ser minoritária).
- **Daemon dos testes de integração roda em `execute`** — inferido de `test_setpoint_inside_limits_still_reaches_dcs` passar hoje sem override. Se um teste novo receber 409 `_MONITOR_DETAIL` inesperado, o fixture do app está em `monitor`: aplicar o override inverso (`lambda: "execute"`) no teste, não mudar o fixture global.
- **`RUNNING_TINT`** (LoopCard `:74-91`): migrar o valor literal que estiver lá. Se outras consts do bloco forem usadas fora dos chips, deixá-las em `LoopCard.tsx`.
- **`statusEnvelope` base** já emite `kp: 1, ti: 10, td: 0` (`fixtures.ts:111-114`) — placeholders testáveis sem mexer no fixture. Se um teste precisar de outro valor, sobrescrever via `Partial<StatusData>` como hoje.
- Badge do card em malha sem `execution_mode` no payload (API velha): `?? 'SUPERVISORY'` (D16) — já embutido na fatia 4b.
