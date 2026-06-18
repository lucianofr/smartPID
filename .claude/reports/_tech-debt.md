# Tech Debt Registry

Track technical debt explicitly like bugs. Review weekly.

---

## Critical (Blocks Feature Work)

_Debt that prevents or significantly slows new development._

- [ ] **TD-001**: `routers/project.py` sem auth/authz
  - **Impact:** Critical - open/import/delete não-autenticado mexe na DCS viva; bloqueia Fatia 7 do web HMI
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

- [ ] **TD-002**: Path traversal via `name` em `project_service`
  - **Impact:** Critical - permite write/delete arbitrário no filesystem; bloqueia Fatia 7 do web HMI
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

<!-- Example:
- [ ] **TD-001**: Legacy auth system needs migration
  - **Impact:** High - blocks SSO integration
  - **Effort:** 2 weeks
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## High (Causes Frequent Issues)

_Debt that causes recurring problems or bugs._

- [ ] **TD-003**: `/commands/tuning` fura guardrails
  - **Impact:** High - sem `clamp_tuning_params`, só `require_operator`, body dict não-tipado; permite escrever sintonia fora dos limites no controlador. Pré-requisito antes de expor tuning cru no web (Fatia 2)
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

- [ ] **TD-004**: Sem CORS/TrustedHost; API binda `0.0.0.0`
  - **Impact:** High - exposição a DNS-rebinding; recomenda-se bind `127.0.0.1` + allow-list/TrustedHost ou SPA single-origin
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

- [ ] **TD-005**: Sem limite de tamanho no upload `.spid` (import)
  - **Impact:** High - `await file.read()` carrega o arquivo inteiro em memória → OOM/DoS. Adicionar limite de tamanho + streaming
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

<!-- Example:
- [ ] **TD-002**: N+1 queries in user dashboard
  - **Impact:** Medium - page load > 5s
  - **Effort:** 3 days
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## Medium (Slows Development)

_Debt that makes development harder but doesn't block._

- [ ] **TD-006**: WS auth via `?token=` (ponte WS futura)
  - **Impact:** Medium - token em query param vaza em log/history; usar ws-ticket de curta duração ou auth na primeira mensagem quando a ponte WS for criada
  - **Source:** arch/arch-web-hmi-20260618.md + security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

<!-- Example:
- [ ] **TD-003**: Test fixtures are brittle
  - **Impact:** Low - flaky CI
  - **Effort:** 1 week
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## Low (Track for Later)

_Known issues not currently prioritized._

<!-- Example:
- [ ] **TD-004**: Could use newer React patterns
  - **Impact:** None - works fine
  - **Effort:** 2 weeks
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

---

## Resolved

_Completed tech debt items. Keep for 90 days then archive._

<!-- Example:
- [x] **TD-000**: Migrated from callbacks to async/await
  - **Resolved:** 2025-01-15
  - **Resolution:** Refactored auth module
-->

---

## Metrics

| Category | Count | Oldest |
|----------|-------|--------|
| Critical | 2 | 2026-06-18 |
| High | 3 | 2026-06-18 |
| Medium | 1 | 2026-06-18 |
| Low | 0 | - |
| **Total Open** | **6** | 2026-06-18 |

_Last updated: 2026-06-18_

---

## Guidelines

### When to Add Debt

Add to registry when you:
- Skip tests to meet deadline
- Use workaround instead of proper fix
- Copy-paste instead of abstract
- Ignore deprecation warnings
- Hard-code instead of configure
- Disable linter rules

### Debt Item Format

```markdown
- [ ] **TD-NNN**: Brief description
  - **Impact:** Critical | High | Medium | Low
  - **Source:** [report-name.md] or [postmortem-name.md] (what identified this debt)
  - **Effort:** Time estimate
  - **Owner:** @username or @unassigned
  - **Created:** YYYY-MM-DD
```

### Priority Guidelines

| Priority | Criteria | Action |
|----------|----------|--------|
| Critical | Blocks features, security risk | Address immediately |
| High | Causes incidents, slows team | Next sprint |
| Medium | Annoying but manageable | Quarterly review |
| Low | Nice to fix someday | Opportunistic |

### Review Cadence

- **Weekly:** Review Critical/High items
- **Sprint planning:** Consider Medium items
- **Quarterly:** Audit full registry, archive resolved

### Commands

```bash
# View debt summary
/debt

# Add new debt item
/debt add "Description" --priority high

# Mark resolved
/debt resolve TD-001
```
