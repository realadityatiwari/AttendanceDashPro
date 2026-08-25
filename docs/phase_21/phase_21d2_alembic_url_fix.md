# AttendanceDash Pro — Phase 21D.2: Alembic URL Interpolation Defect Fix

Status: **COMPLETE** — configuration defect fixed and verified locally. No
database connection, no migration, no mutation.

## 1. Symptom

The first production migration attempt was stopped by a local Alembic
configuration error BEFORE any database connection or migration occurred:

```
ValueError: invalid interpolation syntax in
'postgresql+asyncpg://...%23...?...'
at config.set_main_option("sqlalchemy.url", settings.DATABASE_URI)
```

The `DATABASE_URI` itself was correct (percent-encoded password, `?ssl=require`).

## 2. Root Cause

`backend/alembic/env.py` calls:

```python
config.set_main_option("sqlalchemy.url", settings.DATABASE_URI)
```

Alembic's `Config` object builds its underlying `ConfigParser` with the
**default `BasicInterpolation()`** (Alembic 1.19.1, `config.py` line 246:
`file_config = ConfigParser(self.config_args)`; the `config_args` dict is
passed as *defaults*, so `interpolation=` cannot be injected through the
constructor).

`BasicInterpolation` treats `%` sequences as interpolation markers. When
`set_main_option()` (→ `ConfigParser.set()` → `_interpolation.before_set()`) is
given a value containing `%23` (the URL-encoded `#`), it raises
`ValueError: invalid interpolation syntax`.

`configparser` itself documents the fix: constructing with
`interpolation=None` is normalized to the **no-op `Interpolation()`** class
(CPython 3.13 `configparser.py` lines 667–668). Since Alembic creates its
parser internally, the equivalent clean fix is to replace the parser's
`_interpolation` with that same no-op `Interpolation()` before the URL is set.

## 3. Exact Fix

`backend/alembic/env.py` — added immediately after `config = context.config`:

```python
from configparser import Interpolation

config.file_config._interpolation = Interpolation()
```

- `config.file_config` is a `@util.memoized_property` (Alembic 1.19.1), so the
  parser is created once and this change applies once, before any
  `set_main_option` / `get_main_option` call.
- `Interpolation()` is the no-op base class — `before_set` and `before_get`
  return values unchanged, so the URL passes through verbatim.
- Verified that `ConfigParser.set()` + `.get()` work with `%23` after this
  change (no `AttributeError`, no `ValueError`).

## 4. Why This Is the Right Fix

| Option | Verdict |
|---|---|
| Escape `%` as `%%` in the URL | ❌ Would corrupt the actual URL sent to PostgreSQL |
| URL-decode the password before `set_main_option` | ❌ Changes the value; SQLAlchemy expects an encoded URL |
| Pass `interpolation=None` through `config_args` | ❌ Alembic passes `config_args` as *defaults*, not `interpolation=` (keyword-only) |
| Set `config.file_config._interpolation = Interpolation()` | ✅ Clean, no-op, minimal, preserves the URL verbatim |

## 5. Preservation Guarantees

- SQLAlchemy asyncpg dialect: unchanged (`postgresql+asyncpg://`).
- `?ssl=require`: unchanged (passed through verbatim).
- Environment-driven `DATABASE_URI`: unchanged (`settings.DATABASE_URI`).
- Local development: unchanged (no interpolation issue with the local URL;
  the no-op interpolation applies equally).
- Production Supabase compatibility: now works with `%23` etc.
- Migration architecture: no migration files touched; no new migration.
- Database models / auth / attendance / business logic: untouched.

## 6. Verification (no connection, no migration)

| Check | Result |
|---|---|
| `configparser` behavior reproduced (default → ValueError; `Interpolation()` → OK) | ✅ |
| `ConfigParser.set()` + `get()` with `%23` URL after fix | ✅ PASS |
| Alembic `Config.set_main_option` + `get_main_option` with `%23` URL | ✅ PASS (round-trip retains encoding + `ssl=require`) |
| `alembic heads` with `%23` URL | ✅ `e1f2a3b4c5d6 (head)`, exit 0 |
| `alembic upgrade head --sql` (offline; executes env.py; **no DB connection**) | ✅ exit 0, 289 lines of SQL generated, upgrade to `e1f2a3b4c5d6` present |
| `python -m compileall alembic app` | ✅ PASS |
| `git diff --check` | ✅ PASS (exit 0) |
| Production DB | NOT ACCESSED · NOT MIGRATED · NOT MUTATED |
| Development DB | NOT ACCESSED (no SQL executed against it) |

The offline `--sql` run is the definitive proof: it executes `env.py` fully
(including the module-level `set_main_option`) and generates the migration SQL
without ever opening a database connection.

## 7. Explicit Statement

The failed migration attempt that surfaced this defect **never connected to or
mutated Supabase**. The error occurred locally during configuration loading,
before any network/database operation. This fix changes only the local Alembic
configuration parsing.

## 8. Next Authorized Action

The operator may now re-attempt the production database initialization:

1. Set `$env:DATABASE_URI` to the Supabase Session Pooler URL (password
   percent-encoded, `?ssl=require`).
2. From `backend/`: `python -m alembic upgrade head`.
3. Verify head `e1f2a3b4c5d6`; only schema + `alembic_version` rows created.
4. Continue the 21D.2 runbook (Render → Vercel → env wiring).

Requires explicit authorization for the migration itself.
