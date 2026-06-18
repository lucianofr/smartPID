# Tech Debt Registry

Track technical debt explicitly like bugs. Review weekly.

---

## Critical (Blocks Feature Work)

_Debt that prevents or significantly slows new development._

_No open Critical items. TD-001 and TD-002 resolved on 2026-06-18 (see Resolved)._

<!-- Example:
- [ ] **TD-001**: Legacy auth system needs migration
  - **Impact:** High - blocks SSO integration
  - **Effort:** 2 weeks
  - **Owner:** @unassigned
  - **Created:** 2025-01-01
-->

## High (Causes Frequent Issues)

_Debt that causes recurring problems or bugs._

- [ ] **TD-004**: Sem CORS/TrustedHost; API binda `0.0.0.0`
  - **Impact:** High - exposição a DNS-rebinding; recomenda-se bind `127.0.0.1` + allow-list/TrustedHost ou SPA single-origin
  - **Source:** security/security-web-hmi-20260618.md
  - **Effort:** TBD
  - **Owner:** @unassigned
  - **Created:** 2026-06-18

- [ ] **TD-007**: Converter backend para single-admin / remover RBAC + users router
  - **Impact:** High - decisão de produto (2026-06-18): o sistema passa a ser
    **single-user (um administrador), sem RBAC (mono-usuário)**. Os gates por tier de papel
    do security fix (operator/supervisor/admin) devem colapsar para uma única dependência
    "exige administrador autenticado". A exigência de **auth permanece** (401 sem auth);
    apenas os tiers de papel (403 por papel) são removidos. Concretamente: `routers/users`
    (CRUD) deve ser descontinuado; `POST /commands/optimization` hoje usa `require_operator`
    e deve passar a usar o gate de admin único; idem para os demais comandos/projetos que
    hoje exigem operator/supervisor/admin.
  - **Source:** reconciliação dos web specs / decisão de produto 2026-06-18
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

- [x] **TD-001**: `routers/project.py` sem auth/authz
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** Added role dependencies to every `/project` route
    (current/list → operator; new/open/import/download → supervisor; delete →
    admin). Unauthenticated → 401, wrong role → 403. Tests in
    `tests/core/integration/test_api_project.py`.
    _Nota: com a decisão single-admin (TD-007), estes tiers de papel colapsam para um único
    gate "exige administrador autenticado"; a exigência de auth (401) permanece._

- [x] **TD-002**: Path traversal via `name` em `project_service`
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** Added `ProjectService._safe_project_path()` — strict name
    allow-list (`[A-Za-z0-9._\- ]`, ≤128 chars, no `..`/separators/absolute/NUL)
    plus a resolved-path-inside-`projects_dir` assertion. Applied to
    new/open/import/delete; import also re-validates the derived name from
    `UploadFile.filename`. Router maps `ValueError` → 400. Tests in
    `tests/core/unit/test_project_service.py` and `test_api_project.py`.

- [x] **TD-003**: `/commands/tuning` fura guardrails
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** Brought raw `/commands/tuning` to the `apply-tuning` bar:
    typed `TuningCommand` Pydantic body, each supplied Kp/Ti/Td clamped to the
    controller's `max_tuning_change_pct` via `clamp_tuning_change`, and gate
    raised from `require_operator` to `require_supervisor`. Tests in
    `tests/core/integration/test_api_commands.py::TestWriteTuningCommand`.
    _Nota: com a decisão single-admin (TD-007), o gate `require_supervisor` colapsa para o
    gate de admin único; o clamp e a tipagem permanecem._

- [x] **TD-005**: Sem limite de tamanho no upload `.spid` (import)
  - **Resolved:** 2026-06-18 — branch `fix/backend-security-hardening`
  - **Resolution:** `/project/import` now reads the upload in 1 MB chunks with a
    running byte cap (`CoreSettings.max_upload_bytes`, default 50 MB) and rejects
    oversized uploads with HTTP 413 before buffering/writing. Tests in
    `tests/core/integration/test_api_project.py::TestImportProject`.

<!-- Example:
- [x] **TD-000**: Migrated from callbacks to async/await
  - **Resolved:** 2025-01-15
  - **Resolution:** Refactored auth module
-->

---

## Metrics

| Category | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 2 | 2026-06-18 |
| Medium | 1 | 2026-06-18 |
| Low | 0 | - |
| **Total Open** | **3** | 2026-06-18 |

_Open remaining: TD-004 (CORS/bind, High), TD-007 (single-admin/no-RBAC backend migration,
High), TD-006 (WS token, Medium). TD-004/TD-006 deferidos ao trabalho de packaging
WS/StaticFiles (Fatia 0+1); TD-007 é a migração de produto para single-admin._

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
