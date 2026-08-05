# Login Hardening — `POST /auth/login` — 2026-08-05

**Scope:** close the rate-limit-free and length-cap-free login path identified as
F1 (rate limiting), F3 (adjacent, owned by a peer agent), F4 (length caps) and F5
(timing side channel, investigated, not fixed — see §4) in
`security-vps-exposure-20260805.md`. Files touched, per the cross-task split:
`packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`,
`packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py`,
`tests/core/unit/test_auth_login.py`. No other file was edited.

---

## 1. What was there before

Read `routers/auth.py` first, as required. Findings:

- Request model: `LoginRequest` (`smart_pid_domain/dtos/auth.py:9-11`, pre-edit)
  — `username: str`, `password: str`, no `Field()` constraints, unlike the
  sibling `UserCreate` three lines below which already carried
  `Field(min_length=1, max_length=64/128)`.
- Password comparison: `verify_password()` in
  `adapters/inbound/api/auth.py:15-17` — `bcrypt.checkpw(password.encode(),
  password_hash.encode())`. No passlib, no hashlib, no bare `==` anywhere in
  the comparison path — grep-confirmed across `smart_pid_core` for
  `password_hash|checkpw|verify_password`, only hit is this one `bcrypt.checkpw`
  call plus unrelated `password_hash` field plumbing in `user_repo.py`.
- User fetch: `user_repo.get_by_username(body.username)`
  (`routers/auth.py:37`, pre-edit) — awaited before the compare, short-circuits
  via `user is None or not verify_password(...)`.
- The route did **not** receive a `Request` parameter; had to add one.
- No rate limiting, no attempt tracking anywhere in the router or the file
  it imports from (confirmed by the security-reviewer's grep, independently
  re-confirmed by reading the full file top to bottom).

## 2. Changes made

### `smart_pid_domain/dtos/auth.py:9-11`
```python
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)
```
Edited the existing model in place rather than adding a wrapper `LoginBody` —
the model was trivial to constrain directly and this matches the sibling
`UserCreate`'s existing convention in the same file (`Field(min_length=1,
max_length=...)`), the idiom this change mirrors. `254` is the RFC 5321
mailbox-length ceiling (per the assignment's decision — `username` is treated
as an opaque identifier, not necessarily an email); `200` covers bcrypt's
72-byte internal ceiling with headroom for multi-byte UTF-8 before that
boundary is even reached, so oversized input 422s before ever touching bcrypt.

### `routers/auth.py:5-9, 31-32, 34, 38-86` (new) and `89-108` (route body)
- Added `class LoginRateLimiter` (lines 42-86): sliding-window per-IP counter,
  `dict[str, list[float]]` of monotonic timestamps, pruned to the trailing 60s
  on every `check()` call. `check(ip)` appends the current attempt then raises
  `HTTPException(429)` once the pruned+appended count exceeds 5;
  `record_success(ip)` clears that IP's list outright. `clock: Callable[[],
  float] = time.monotonic` is injectable, defaulting to the real clock — this
  is what lets the unit tests avoid real sleeping.
- `login()` now takes `request: Request` (line 91), reads
  `client_ip = request.client.host if request.client else "unknown"` (line 99)
  — **not** `X-Forwarded-For**, single-line comment at lines 97-98 explains why
  (no reverse proxy in front of this deployment; trusting a client-supplied
  header would let the limiter be spoofed).
- `limiter = request.app.state.login_rate_limiter` (line 100), mirroring the
  exact idiom every other route in this file (and `dependencies.py`) already
  uses for state pulled off `app.state` — e.g. `get_settings`/`get_user_repo`
  read `request.app.state.settings`/`.user_repo`. Kept as a plain local read
  rather than a new `Depends()` function since the assignment specifies the
  router owns the limiter end-to-end and every other call site in this file
  that needs `request.app.state.*` already does it this way in `dependencies.py`.
- `limiter.check(client_ip)` runs immediately after the IP is resolved, before
  `user_repo.get_by_username()` — so a caller over budget never reaches the
  database or bcrypt at all.
- `limiter.record_success(client_ip)` runs immediately after the credential
  check passes, before token minting.
- Structured log line `logger.warning("login_rate_limited", client_ip=ip)`
  inside `LoginRateLimiter.check()` on the 429 path — `structlog.get_logger()`
  at module scope (line 34), matching the project-wide convention referenced
  in the task brief; snake_case event name, no leading underscore.

### Cross-agent dependency (not my file)
`app.state.login_rate_limiter` is attached in `app.py`'s `create_app()`, owned
by the peer working that file (confirmed live via hub message — they added
`app.state.login_rate_limiter = auth.LoginRateLimiter()` next to the other
state assignments and re-ran their own suite green). Verified independently
after their change landed by re-running every `/auth/login`-touching test in
the repo (see §3) — all pass with the real, non-injected clock.

## 3. Constant-time compare — investigated, not changed

Step 5 of the assignment asked to replace a plain `==` byte-compare with
`hmac.compare_digest` "ONLY for the byte-level compare," and explicitly not to
double-wrap `bcrypt`'s already-constant-time `verify`. Grepped
`smart_pid_core` for every hash/password comparison site
(`password_hash|checkpw|verify_password|==.*hash`): the only comparison is
`bcrypt.checkpw()` in `adapters/inbound/api/auth.py:17` — `bcrypt`'s C
extension performs a constant-time comparison internally; there is no `==` on
raw bytes anywhere in this codebase's login path to replace. **No code change
made for this step** — wrapping an already constant-time call would be the
double-wrap the assignment explicitly said not to do. This file
(`adapters/inbound/api/auth.py`) was not otherwise touched: it belongs to
neither my owned path nor any of the other three agents' owned paths per the
cross-task split, and the only change it could have taken (the compare) turned
out not to be needed.

Left open, and *not* addressed by this change (out of scope — not named in the
seven `Change` steps): F5's timing side channel, where `user is None` skips
`bcrypt` entirely and returns in microseconds vs. a real username's
tens-of-milliseconds bcrypt round. Tracked in Proposed tech debt below.

## 4. Test outcomes

`tests/core/unit/test_auth_login.py` (new) — 8 tests, all green:

- `TestLoginRateLimiter` (3, pure unit, `_FakeClock`, no sleeping):
  - `test_sixth_check_within_window_raises_429` — 5 `check()` calls pass, 6th
    raises `HTTPException(429)`.
  - `test_check_allowed_again_once_window_elapses` — after 5 calls, advancing
    the fake clock by 61s allows a 6th (sliding-window prune works).
  - `test_record_success_resets_budget` — after 5 calls, `record_success()`
    then a 6th `check()` does not raise.
- `TestLoginRoute` (5, full ASGI route via the `client` fixture):
  - `test_sixth_wrong_attempt_returns_429` — 5x wrong password → 401 each,
    6th → 429 (real `time.monotonic` clock, no sleeping needed since all 6
    requests complete in milliseconds).
  - `test_successful_logins_reset_budget_each_time` — 6 consecutive **correct**
    logins all return 200, proving `record_success` resets the budget on every
    success rather than only once.
  - `test_oversize_username_returns_422` / `test_oversize_password_returns_422`
    — 255-char username / 201-byte password each 422 straight from Pydantic,
    never reaching the route body (confirmed: these two pass even before the
    rate-limiter dependency existed, since FastAPI validates the body before
    calling the endpoint).

Command run: `uv run pytest tests/core/unit/test_auth_login.py -q` →
**8 passed**.

Regression check (broader than the assignment's minimum, to validate the
cross-agent `app.state.login_rate_limiter` dependency landed correctly):
`uv run pytest tests/core/unit/test_auth_login.py
tests/core/unit/test_auth_utils.py tests/core/integration/test_api_auth.py
tests/core/integration/test_auth_role_revocation.py
tests/core/integration/test_api_users.py -q` → **50 passed**.

Full-suite regression (`uv run pytest tests/core -q`) → **1470 passed**, 62
pre-existing warnings unrelated to this change (event-loop-closed thread noise
from `aiosqlite` teardown, an `InsecureKeyLengthWarning` from a deliberately
short test JWT secret, one `coroutine never awaited` in an unrelated
`SystemEventWorker` mock test) — none introduced by this change. No test
needed editing.

## Proposed tech debt

*(For the coordinator to transcribe into `.claude/reports/_tech-debt.md`.)*

- **`LoginRateLimiter` is in-memory and single-process.** A daemon restart
  (or, if this ever moves to multiple uvicorn workers) resets the budget —
  acceptable for this single-process control-plane daemon today, but call it
  out before scaling the deployment. Upgrade path: a shared store (Redis) if
  a second process/worker is ever introduced.
- **No per-username lockout — intentional, not a gap to close later.** The
  limiter is keyed on IP only, on purpose, to avoid a username-enumeration
  side channel (a per-username lockout would let a caller learn valid
  usernames by watching which ones lock differently). The direct consequence:
  a distributed credential-spray (many source IPs, one target username) is
  entirely uncovered by this layer — this is the only brute-force coverage a
  single-IP-keyed limiter can offer, and it is a deliberate trade, not an
  oversight.
- **F5 (login timing side channel) remains open.** `user is None` still skips
  `bcrypt.checkpw` entirely in `adapters/inbound/api/auth.py`/`routers/auth.py`,
  so a nonexistent-username request returns in microseconds vs. a real
  username's tens-of-milliseconds bcrypt round. Not addressed here — it was
  not one of the seven `Change` steps in this assignment, and the file it
  would touch (`adapters/inbound/api/auth.py`) is outside every agent's
  explicitly owned path this round. Low priority while only one account
  (`admin`) exists (per the original report); becomes real the moment a
  second account is created via `POST /users`.

## `files_modified`

- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py`
- `tests/core/unit/test_auth_login.py` (new)
