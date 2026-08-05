# Bootstrap admin password fix — 20260805

Agent: BootstrapAdminFix (backend). Scope: `packages/smart_pid_core/src/smart_pid_core/main.py`
only, per the cross-task contract (Agent A). Closes TD-011.

## Problem

`main.py::_seed_default_admin` minted `admin`/`admin` unconditionally on a fresh
`users.db` and logged the literal password:

```
SECURITY: Default admin account created with password 'admin'. Change it immediately.
```

A fresh deployment left on the public internet with default credentials and
no forced rotation is a trivial compromise (F1, security-vps-exposure-20260805.md).

## Change applied

File: `packages/smart_pid_core/src/smart_pid_core/main.py`

- Line 6-7 (new imports): added `import os` and `import secrets`.
- Line 101-128 (`_seed_default_admin`, was 99-109): behaviour is now:
  1. `users.db` non-empty → no-op, unchanged.
  2. `users.db` empty AND `SPID_BOOTSTRAP_ADMIN_PASSWORD` set → seed `admin`
     with that value verbatim (no length cap). Logs one WARNING
     (`seeded_default_admin`) that an explicit override is in effect; the
     password value itself is never included in the log line, since the
     operator who set the env var already knows it.
  3. `users.db` empty AND the env var is unset → seed `admin` with
     `secrets.token_urlsafe(12)` (~16-22 url-safe base64 chars from 12 random
     bytes) and log exactly one WARNING with event name
     `bootstrap_admin_password` whose message embeds the generated password
     and the retrieval hint `docker logs smartpid | grep
     bootstrap_admin_password`. This is deliberate: unlike path 2, this is
     the *only* place the password exists, so it must be recoverable from
     the log, once, or the freshly bootstrapped admin account is unusable.

Diff (`git diff -- packages/.../main.py`):

```
+import os
+import secrets
...
-    """Create the default admin account when users.db has no rows."""
+    """Create the default admin account when users.db has no rows.
+
+    Password source, in order: ``SPID_BOOTSTRAP_ADMIN_PASSWORD`` env var if
+    set (operator's explicit choice, never logged), else a fresh
+    ``secrets.token_urlsafe(12)`` value logged once at WARNING so an
+    operator can recover it from `docker logs smartpid`.
+    """
     if await user_repo.list_all():
         return
-    admin_hash = hash_password("admin")
+    env_password = os.environ.get("SPID_BOOTSTRAP_ADMIN_PASSWORD")
+    if env_password:
+        admin_password = env_password
+        logger.warning(
+            "seeded_default_admin",
+            msg="Bootstrap admin password set via SPID_BOOTSTRAP_ADMIN_PASSWORD "
+            "env var. Change it after first login if it was not generated "
+            "specifically for this deployment.",
+        )
+    else:
+        admin_password = secrets.token_urlsafe(12)
+        logger.warning(
+            "bootstrap_admin_password",
+            msg=f"Generated one-time admin password: {admin_password}. "
+            "Read it from: docker logs smartpid | grep bootstrap_admin_password",
+        )
+    admin_hash = hash_password(admin_password)
     await user_repo.create("admin", admin_hash, UserRole.ADMIN.value)
-    logger.warning(
-        "seeded_default_admin",
-        msg="SECURITY: Default admin account created with password 'admin'. "
-        "Change it immediately.",
-    )
```

No changes outside `main.py`.

## New env knob

`SPID_BOOTSTRAP_ADMIN_PASSWORD` — optional, unset by default. Read once, at
first boot, only when `users.db` has zero rows. If set, its value is used
verbatim as the seeded `admin` password (no length cap beyond what
`hash_password`/bcrypt itself enforces — bcrypt truncates at 72 bytes, an
existing property of the hashing function, not new here). If unset, a random
`secrets.token_urlsafe(12)` password is generated and logged once at WARNING.

## Test changes

File: `tests/core/integration/test_user_role_migration.py`
(`_seed_default_admin` is imported and tested here already; no
`tests/core/unit/test_main.py` exists in this repo — grepped for
`_seed_default_admin` / `Default admin account` to confirm this is the only
call site and the only test file exercising it, per the assignment's own
"find it by grepping" instruction).

`TestSeedDefaultAdmin` rewritten from 2 tests to 3:

- `test_generated_password_is_not_admin_and_is_logged` — asserts the seeded
  hash does NOT verify against `"admin"` (criterion a) and that
  `bootstrap_admin_password` appears in captured stdout (criterion c). Uses
  `capsys`, not `caplog`: this module's `logger = structlog.get_logger()`
  renders via structlog's default `ConsoleRenderer` straight to stdout in
  this test environment (confirmed empirically — `caplog.text` was empty
  while `capsys` captured the line), unlike the stdlib
  `logging.getLogger(__name__)` loggers other test files capture with
  `caplog`.
- `test_env_var_password_used_verbatim_and_not_logged` — asserts the env var
  path (criterion b) hashes the exact env value and that the raw value never
  appears in stdout.
- `test_noop_when_users_exist` — unchanged behaviour, now also clears the
  env var via `monkeypatch` so a leaked env var from a prior test can't
  change this test's seeded credential (it's a no-op path so it wouldn't
  actually run the password branch, but kept explicit for clarity).

All three use `monkeypatch.setenv`/`delenv` for `SPID_BOOTSTRAP_ADMIN_PASSWORD`
so tests are isolated from the real process environment and from each other.

## Test results

```
$ uv run pytest tests/core/integration/test_user_role_migration.py -q
.......
7 passed in 1.67s
```

(7 = the pre-existing `TestRoleValueMigration` (3) + `TestDDLDefault` (1) +
the new `TestSeedDefaultAdmin` (3).) The ticket's suggested command
`uv run pytest tests/core/unit/test_main.py -q` targets a file that does not
exist in this repo; the actual test file was located by grep as instructed
and run instead.

Full-suite regression check (`uv run pytest tests/core -q`, not required by
the ticket but run to confirm "no regressions" per the constraint): 1449
passed. 7 failures + 7 errors, all `AttributeError: 'State' object has no
attribute 'login_rate_limiter'` in `test_api_auth.py`, `test_api_users.py`,
`test_auth_role_revocation.py` — these are pre-existing, from a peer agent's
in-flight `app.state.login_rate_limiter` work on `auth.py`/`app.py` (git
status shows both files modified outside this agent's diff, owned by a
different agent per the cross-task contract). Confirmed unrelated: grepped
those three failing test files for `_seed_default_admin` and
`SPID_BOOTSTRAP_ADMIN_PASSWORD` — zero matches. Not this agent's scope to
fix.

## Files modified

- `packages/smart_pid_core/src/smart_pid_core/main.py`
- `tests/core/integration/test_user_role_migration.py`

## Proposed tech debt

Transcribe into `_tech-debt.md`, mark TD-011 resolved by this change, and add:

- **TD-012 (new)**: `/auth/login` has no rate limiting or lockout. This fix
  removes the *guessable* default credential, but a brute-force actor can
  still hammer `/auth/login` against any weak or leaked password — including
  a weak explicit `SPID_BOOTSTRAP_ADMIN_PASSWORD` (see below) — with zero
  friction. Owned by Agent C's concurrent rate-limit work
  (`request.app.state.login_rate_limiter`, 5/min/IP) per today's cross-task
  contract; this is not fixed by this change and should stay open until that
  work lands and is verified.
- **TD-013 (new)**: `SPID_BOOTSTRAP_ADMIN_PASSWORD=admin` (or any other weak
  value) still seeds a weak admin password by explicit operator choice. This
  is not a defect of this fix — the knob exists precisely so an operator can
  set a known password for automation/testing — but it re-opens the same
  exposure this fix closes if an operator sets it carelessly in a public
  deployment. Defense-in-depth opportunity (not required by this ticket):
  reject or warn loudly if the env value matches a small deny-list
  (`admin`, `password`, `changeme`, etc.) or is below some minimum length,
  the same way a "weak password" check would apply to any user-set
  credential.
