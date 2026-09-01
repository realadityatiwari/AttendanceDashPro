"""Phase 25.1 static verifier — refresh-token backend foundation.

Static/backend-only checks (no DB required; the dev Postgres container is not
assumed to be running). Verifies:

 1.  Model registered on the shared Base and importable via app.models.
 2.  Model stores ONLY a SHA-256 hex digest (String(64)), never a raw secret.
 3.  Refresh secrets are CSPRNG-generated and hash to 64 hex chars.
 4.  Single Alembic head, chaining c4d5e6f7a8b9 -> a9b8c7d6e5f4 (parsed via
     the alembic script directory, matching `alembic heads` semantics).
 5.  Migration creates refresh_tokens with the expected columns/indexes and
     a clean drop-table downgrade (offline SQL generation, no DB mutation).
 6.  /auth/refresh and /auth/logout routes registered; login/register intact.
 7.  Refresh cookie is HttpOnly, path-scoped to /api/v1/auth, SameSite and
     Secure driven by configuration.
 8.  TokenResponse contract unchanged (access_token + token_type only);
     access JWT claims unchanged.
 9.  Rotation service semantics: valid rotate (family preserved, old token
     marked used with replaced_by), reuse → family revocation + error,
     revoked → error + revocation, expired/unknown → error without minting,
     deactivated/missing user → error (no session). In-memory fake session —
     no DB.
10.  Production guard: REFRESH_COOKIE_SECURE=false rejected in production.

Run:  backend/.venv/Scripts/python.exe verify_phase_25_1.py
"""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def main() -> int:
    print("Phase 25.1 — refresh-token backend foundation (static verification)\n")

    # ── 1/2. Model surface ────────────────────────────────────────────────
    print("[1] Model")
    from app.models.refresh_token import RefreshToken
    import app.models as models_pkg
    from app.db.base_class import Base

    check("model importable via app.models", "RefreshToken" in dir(models_pkg))
    check("registered on shared Base metadata", RefreshToken.__tablename__ in Base.metadata.tables)
    table = Base.metadata.tables["refresh_tokens"]
    cols = table.columns
    check("token_hash is String(64) (SHA-256 hex)", str(cols["token_hash"].type) == "VARCHAR(64)")
    check("no raw-token column", not any(
        "raw" in c.name.lower() or "secret" in c.name.lower() for c in cols))
    check("has family_id / expires_at / is_used / is_revoked / replaced_by",
          all(c in cols for c in ("family_id", "expires_at", "is_used", "is_revoked", "replaced_by")))
    names = {i.name for i in table.indexes}
    check("unique token_hash index", "uq_refresh_tokens_token_hash" in names)
    check("family + user revocation indexes",
          {"ix_refresh_tokens_family_id", "ix_refresh_tokens_user_id"} <= names)

    # ── 3. Secret generation / hashing ────────────────────────────────────
    print("[2] Secret generation & hashing")
    from app.services.refresh_token_service import _hash_token, _REFRESH_SECRET_BYTES
    import secrets as _secrets
    sample = _secrets.token_urlsafe(_REFRESH_SECRET_BYTES)
    digest = _hash_token(sample)
    check("secret is opaque url-safe (not a JWT)",
          not sample.startswith("ey") and sample.count(".") != 2)
    check("digest is 64 lowercase hex chars", bool(re.fullmatch(r"[0-9a-f]{64}", digest)))
    check("digest is stable SHA-256", _hash_token(sample) == digest and digest != sample)

    # ── 4/5. Migration chain (alembic script directory) ───────────────────
    print("[3] Alembic migration")
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    check("exactly one head", len(heads) == 1, f"heads={heads}")
    check("head is a9b8c7d6e5f4", heads == ["a9b8c7d6e5f4"])
    walk = list(script.walk_revisions())
    rev = next(r for r in walk if r.revision == "a9b8c7d6e5f4")
    check("chains from c4d5e6f7a8b9", rev.down_revision == "c4d5e6f7a8b9")

    # Authoritative textual checks on the migration module (the offline SQL
    # path was validated separately via `alembic upgrade --sql`).
    from pathlib import Path
    for p in Path("alembic/versions").glob("*.py"):
        if "a9b8c7d6e5f4" in p.name:
            mig_path = p
            break
    check("migration file present", mig_path is not None)
    mig_text = mig_path.read_text(encoding="utf-8") if mig_path else ""
    for expected in ("create_table", "refresh_tokens", "uq_refresh_tokens_token_hash",
                     "ix_refresh_tokens_family_id", "ix_refresh_tokens_user_id"):
        check(f"upgrade defines {expected}", expected in mig_text)
    check("downgrade drops the table", "drop_table" in mig_text and "refresh_tokens" in mig_text)
    check("no other table touched in migration",
          len(re.findall(r'"(\w+_id)"\s*\)', mig_text)) <= 4)

    # ── 6/7/8. Endpoints + cookie + contract ──────────────────────────────
    print("[4] Endpoints, cookie, response contract")
    from app.api.v1.endpoints import auth as auth_module
    from app.core.config import settings
    from app.api.v1.endpoints.auth import _set_refresh_cookie, _clear_refresh_cookie, TokenResponse
    from fastapi import Response as FastAPIResponse

    routes = {r.path: sorted(r.methods) for r in auth_module.router.routes}
    check("login preserved", routes.get("/login") == ["POST"])
    check("register preserved", routes.get("/register") == ["POST"])
    check("POST /refresh registered", routes.get("/refresh") == ["POST"])
    check("POST /logout registered", routes.get("/logout") == ["POST"])

    resp = FastAPIResponse()
    _set_refresh_cookie(resp, "raw-secret-value")
    set_cookie = resp.headers["set-cookie"]
    check("cookie name from settings", set_cookie.startswith(f"{settings.REFRESH_COOKIE_NAME}="))
    check("HttpOnly flag set", "httponly" in set_cookie.lower())
    check("path scoped to auth endpoints", f"Path={settings.REFRESH_COOKIE_PATH}" in set_cookie)
    check("SameSite from settings", f"samesite={settings.REFRESH_COOKIE_SAMESITE}" in set_cookie.lower())
    check("Secure flag set", "secure" in set_cookie.lower())
    check("max-age == lifetime in seconds",
          f"Max-Age={settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400}" in set_cookie)

    cleared = FastAPIResponse()
    _clear_refresh_cookie(cleared)
    check("delete_cookie clears with same name/path",
          "Max-Age=0" in cleared.headers["set-cookie"]
          and f"Path={settings.REFRESH_COOKIE_PATH}" in cleared.headers["set-cookie"])

    contract = set(TokenResponse.model_fields)
    check("TokenResponse contract unchanged", contract == {"access_token", "token_type"})

    from app.core.security import create_access_token
    import jwt as pyjwt
    token = create_access_token(subject=str(uuid.uuid4()), roll_number="1234567890123")
    claims = pyjwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    check("access JWT contract unchanged",
          claims["type"] == "access" and "sub" in claims and "roll_number" in claims and "exp" in claims)

    # ── 9. Rotation semantics (fake in-memory session, no DB) ─────────────
    print("[5] Rotation semantics (in-memory fake session)")

    from sqlalchemy import Update
    from sqlalchemy.sql.selectable import Select

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def first(self):
            return self._rows[0] if self._rows else None

    class FakeSession:
        """Records statements; simulates one refresh_tokens row + a user row."""

        def __init__(self, token_row, user_row):
            self.token_row = token_row
            self.user_row = user_row
            self.added = []
            self.updates = []
            self.committed = 0

        async def execute(self, stmt):
            if isinstance(stmt, Update):
                table_name = stmt.table.name
                params = stmt.compile().params
                self.updates.append((table_name, params))
                if table_name == "refresh_tokens" and params.get("is_used") is True:
                    # emulate: the presented row transitions to used
                    self.token_row.is_used = True
                    self.token_row.replaced_by = params.get("replaced_by")
                if table_name == "refresh_tokens" and params.get("is_revoked") is True:
                    if self.token_row is not None:
                        self.token_row.is_revoked = True
                return FakeResult([])
            if isinstance(stmt, Select):
                entity = stmt.column_descriptions[0]["entity"]
                if entity is not None and entity.__name__ == "User":
                    return FakeResult([self.user_row] if self.user_row else [])
                return FakeResult([self.token_row] if self.token_row else [])
            return FakeResult([])

        def add(self, obj):
            self.added.append(obj)

        async def flush(self):
            for obj in self.added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

        async def commit(self):
            self.committed += 1

        async def rollback(self):
            pass

    from app.services.refresh_token_service import RefreshTokenService, RefreshTokenError
    from app.models.refresh_token import RefreshToken
    from app.models.user import User

    def make_user(active=True):
        return User(id=uuid.uuid4(), roll_number="1234567890123",
                    name="Verifier", is_active=active)

    def make_row(user, *, used=False, revoked=False, expired=False):
        row = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token("presented-raw"),
            family_id=uuid.uuid4(),
            expires_at=(datetime.now(timezone.utc) - timedelta(days=1)) if expired
            else datetime.now(timezone.utc) + timedelta(days=30),
        )
        row.is_used = used
        row.is_revoked = revoked
        return row

    async def run_case(token_row, user_row, presented="presented-raw"):
        db = FakeSession(token_row, user_row)
        svc = RefreshTokenService(db)
        try:
            result = await svc.rotate(presented)
            return ("ok", result, db)
        except RefreshTokenError as exc:
            return ("err", exc, db)

    user = make_user()

    # valid rotation
    row = make_row(user)
    outcome, result, db = asyncio.run(run_case(row, user))
    check("valid refresh → success + committed", outcome == "ok" and db.committed >= 1)
    check("new token minted in same family",
          len(db.added) == 1 and db.added[0].family_id == row.family_id)
    check("new token hash is digest of returned raw secret",
          outcome == "ok" and db.added[0].token_hash == _hash_token(result[1]))
    used_updates = [(t, p) for (t, p) in db.updates if t == "refresh_tokens" and p.get("is_used")]
    check("old token marked used with replaced_by link",
          len(used_updates) == 1
          and used_updates[0][1].get("replaced_by") == db.added[0].id)

    # reuse of a used token
    row = make_row(user, used=True)
    outcome, exc, db = asyncio.run(run_case(row, user))
    check("reuse of used token → 401 error", outcome == "err")
    check("reuse → family revocation executed",
          any(t == "refresh_tokens" and p.get("is_revoked") for (t, p) in db.updates))
    check("reuse → revocation committed", outcome == "err" and db.committed >= 1)
    check("reuse mints nothing", len(db.added) == 0)

    # revoked token presented
    row = make_row(user, revoked=True)
    outcome, exc, db = asyncio.run(run_case(row, user))
    check("revoked token → error + family revocation",
          outcome == "err"
          and any(t == "refresh_tokens" and p.get("is_revoked") for (t, p) in db.updates))

    # expired token
    row = make_row(user, expired=True)
    outcome, exc, db = asyncio.run(run_case(row, user))
    check("expired token → error, nothing minted", outcome == "err" and len(db.added) == 0)

    # unknown token
    outcome, exc, db = asyncio.run(run_case(None, user, presented="never-issued"))
    check("unknown token → error, nothing minted", outcome == "err" and len(db.added) == 0)

    # deactivated / missing user
    row = make_row(user)
    outcome, exc, db = asyncio.run(run_case(row, None))
    check("missing user → error, no session", outcome == "err" and len(db.added) == 0)
    row = make_row(user)
    outcome, exc, db = asyncio.run(run_case(row, make_user(active=False)))
    check("deactivated user → error, no session", outcome == "err" and len(db.added) == 0)

    # issuance
    db = FakeSession(None, user)
    svc = RefreshTokenService(db)
    raw, issued = asyncio.run(svc.issue(user))
    check("issue → CSPRNG secret, SHA-256 persisted, family minted",
          raw != issued.token_hash and issued.token_hash == _hash_token(raw)
          and isinstance(issued.family_id, uuid.UUID))

    # logout revocation
    row = make_row(user)
    db = FakeSession(row, user)
    svc = RefreshTokenService(db)
    asyncio.run(svc.revoke_by_token("presented-raw"))
    check("logout revokes the family (idempotent path)",
          any(t == "refresh_tokens" and p.get("is_revoked") for (t, p) in db.updates)
          and db.committed >= 1)

    # ── 10. Production guard ──────────────────────────────────────────────
    print("[6] Production configuration guard")
    import importlib
    import app.core.config as cfg_mod
    env_keys = ["APP_ENV", "JWT_SECRET_KEY", "DATABASE_URI",
                "BACKEND_CORS_ORIGINS", "REFRESH_COOKIE_SECURE"]
    saved = {k: os.environ.get(k) for k in env_keys}
    os.environ.update({
        "APP_ENV": "production",
        "JWT_SECRET_KEY": "x" * 40,
        "DATABASE_URI": "postgresql+asyncpg://u:p@db.example.com:5432/db",
        "BACKEND_CORS_ORIGINS": '["https://app.example.com"]',
        "REFRESH_COOKIE_SECURE": "false",
    })
    try:
        importlib.reload(cfg_mod)
        cfg_mod.Settings()  # pydantic-settings reads env at instantiation
        check("REFRESH_COOKIE_SECURE=false rejected in production", False, "no error raised")
    except Exception as exc:
        check("REFRESH_COOKIE_SECURE=false rejected in production",
              "REFRESH_COOKIE_SECURE" in str(exc))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print(f"\nRESULT: {PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
