"""Phase 2A (H-4a/H-4c) — bounded inbox reads + orphan-proof projections.

Two layers:

1. DB-free:
   - page-size clamping (default 50, max 200, min 1);
   - the bounded statement shape (LIMIT/OFFSET, deterministic
     created_at DESC / id DESC ordering, live-event EXISTS guard);
   - the service's pagination metadata (total/limit/offset/has_more) and
     per-page cache keys, against a stub repository.

2. Sandboxed real DB (savepoint rollback — same pattern as
   test_registration_enrollment_e2e): ordering and page boundaries, live rows
   remain visible, dismissed rows and orphaned event projections cannot
   surface, and the unread badge matches the visible live set. Nothing
   persists: every scenario runs inside a transaction that is rolled back.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
import asyncio
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.db.base_class import IST
from app.db.session import AsyncSessionLocal
from app.models.enums import EventType, NotificationKind
from app.models.event import AcademicEvent
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repo import (
    DEFAULT_INBOX_PAGE_SIZE,
    MAX_INBOX_PAGE_SIZE,
    NotificationRepository,
    clamp_inbox_page_size,
)
from app.services.notification_service import NotificationService, _notification_cache


# ════════════════════════════════════════════════════════════════════════════
# DB-free: clamping, statement shape, service metadata
# ════════════════════════════════════════════════════════════════════════════

def test_page_size_clamping_boundaries():
    assert clamp_inbox_page_size(None) == DEFAULT_INBOX_PAGE_SIZE
    assert clamp_inbox_page_size(DEFAULT_INBOX_PAGE_SIZE) == DEFAULT_INBOX_PAGE_SIZE
    assert clamp_inbox_page_size(1) == 1
    assert clamp_inbox_page_size(0) == 1
    assert clamp_inbox_page_size(-50) == 1
    assert clamp_inbox_page_size(MAX_INBOX_PAGE_SIZE) == MAX_INBOX_PAGE_SIZE
    assert clamp_inbox_page_size(MAX_INBOX_PAGE_SIZE + 1) == MAX_INBOX_PAGE_SIZE
    assert clamp_inbox_page_size(10 ** 9) == MAX_INBOX_PAGE_SIZE
    assert clamp_inbox_page_size("nonsense") == DEFAULT_INBOX_PAGE_SIZE


class _CapturingSession:
    """Captures the statement instead of executing it."""

    def __init__(self):
        self.statements = []

    async def execute(self, stmt, *a, **k):
        self.statements.append(stmt)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))


def _inbox_statement(limit, offset):
    db = _CapturingSession()
    asyncio.run(NotificationRepository(db).get_inbox(uuid.uuid4(), limit=limit, offset=offset))
    return db.statements[-1]


def test_inbox_statement_is_always_bounded():
    stmt = _inbox_statement(10 ** 9, 0)
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    # page size clamped to the explicit maximum; never unbounded
    assert stmt._limit_clause.value == MAX_INBOX_PAGE_SIZE
    assert stmt._offset_clause.value == 0
    assert "LIMIT" in sql
    # deterministic newest-first ordering
    assert "ORDER BY notifications.created_at DESC, notifications.id DESC" in sql
    # dismissed rows and orphaned event projections are filtered in SQL
    assert "notifications.is_dismissed" in sql
    assert "EXISTS" in sql and "academic_events" in sql


def test_inbox_statement_applies_requested_page_and_offset():
    stmt = _inbox_statement(25, 50)
    assert stmt._limit_clause.value == 25
    assert stmt._offset_clause.value == 50


class _StubRepo:
    def __init__(self, rows, total, unread):
        self.rows = rows
        self.total = total
        self.unread = unread
        self.calls = []

    async def get_inbox(self, user_id, *, limit, offset):
        self.calls.append((limit, offset))
        # The stub models "this page's rows": offsets are asserted via
        # `calls`, page contents via `rows`.
        return self.rows[:limit]

    async def count_unread(self, user_id):
        return self.unread

    async def count_inbox(self, user_id):
        return self.total


def _stub_row(i):
    return SimpleNamespace(
        id=uuid.uuid4(),
        kind=NotificationKind.MUST_ATTEND,
        occurrence_key=f"SUBJ-{i}",
        date=date(2026, 9, 1),
        subject_code=f"SUBJ-{i}",
        subject_name=f"Subject {i}",
        message=f"message {i}",
        session_id=None,
        quiz_cycle=None,
        event_id=None,
        is_read=False,
    )


def _service_with(repo):
    svc = NotificationService(None)  # constructors only store the session
    svc.notification_repo = repo
    return svc


def test_service_clamps_page_size_and_reports_metadata():
    user = SimpleNamespace(id=uuid.uuid4())
    repo = _StubRepo([_stub_row(i) for i in range(5)], total=137, unread=9)
    svc = _service_with(repo)
    _notification_cache.clear()

    resp = asyncio.run(svc.get_notifications(user, limit=10 ** 6, offset=0))

    assert repo.calls == [(MAX_INBOX_PAGE_SIZE, 0)]
    assert resp.limit == MAX_INBOX_PAGE_SIZE
    assert resp.offset == 0
    assert resp.total == 137
    assert resp.unread_count == 9
    assert resp.has_more is True
    assert len(resp.items) == 5


def test_service_has_more_false_at_last_page_and_empty_inbox():
    user = SimpleNamespace(id=uuid.uuid4())
    repo = _StubRepo([_stub_row(i) for i in range(10)], total=30, unread=0)
    svc = _service_with(repo)
    _notification_cache.clear()

    last = asyncio.run(svc.get_notifications(user, limit=20, offset=20))
    assert repo.calls == [(20, 20)]
    assert last.offset == 20 and last.has_more is False  # 20 + 10 == total

    empty_repo = _StubRepo([], total=0, unread=0)
    empty_svc = _service_with(empty_repo)
    _notification_cache.clear()
    empty = asyncio.run(empty_svc.get_notifications(user, limit=50, offset=0))
    assert empty.items == [] and empty.has_more is False and empty.total == 0


def test_service_clamps_negative_offset_to_zero():
    user = SimpleNamespace(id=uuid.uuid4())
    repo = _StubRepo([], total=0, unread=0)
    svc = _service_with(repo)
    _notification_cache.clear()
    resp = asyncio.run(svc.get_notifications(user, limit=10, offset=-5))
    assert repo.calls == [(10, 0)]
    assert resp.offset == 0


def test_service_caches_pages_independently():
    user = SimpleNamespace(id=uuid.uuid4())
    repo = _StubRepo([_stub_row(i) for i in range(30)], total=100, unread=0)
    svc = _service_with(repo)
    _notification_cache.clear()

    asyncio.run(svc.get_notifications(user, limit=10, offset=0))
    asyncio.run(svc.get_notifications(user, limit=10, offset=10))
    assert len(repo.calls) == 2
    # Re-requesting a cached page does not re-hit the repository.
    asyncio.run(svc.get_notifications(user, limit=10, offset=0))
    assert len(repo.calls) == 2


# ════════════════════════════════════════════════════════════════════════════
# Sandboxed real DB (savepoint rollback): ordering, boundaries, live vs orphan
# ════════════════════════════════════════════════════════════════════════════

class _RollbackSession:
    """commit() -> flush inside the outer transaction; everything rolls back."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def commit(self):
        await self._real.flush()

    async def rollback(self):
        await self._real.rollback()


# ONE loop for the whole module (asyncpg connections bind to their creating
# loop; the registration e2e module documents the same Windows constraint).
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _loop_lifecycle():
    yield
    try:
        from app.db.session import engine
        _LOOP.run_until_complete(engine.dispose())
    except Exception:
        pass
    _LOOP.close()


def _new_roll():
    return f"230{uuid.uuid4().int % 10**10:010d}"


def _notification(user_id, *, key, created_at, kind=NotificationKind.MUST_ATTEND,
                  event_id=None, is_read=False, is_dismissed=False):
    return Notification(
        user_id=user_id,
        kind=kind,
        occurrence_key=key,
        date=date(2026, 9, 1),
        message=f"message {key}",
        subject_code=None,
        subject_name=None,
        event_id=event_id,
        is_read=is_read,
        is_dismissed=is_dismissed,
        created_at=created_at,
    )


def test_inbox_ordering_and_page_boundaries_real_db():
    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            try:
                user = User(roll_number=_new_roll(), name="H4c Pagination")
                session.add(user)
                await session.flush()
                base = datetime.now(IST)
                for i in range(5):
                    session.add(_notification(
                        user.id, key=f"P{i}",
                        created_at=base - timedelta(minutes=5 - i),
                    ))
                await session.flush()

                repo = NotificationRepository(session)
                page1 = await repo.get_inbox(user.id, limit=2, offset=0)
                page2 = await repo.get_inbox(user.id, limit=2, offset=2)
                page3 = await repo.get_inbox(user.id, limit=2, offset=4)
                page4 = await repo.get_inbox(user.id, limit=2, offset=6)
                total = await repo.count_inbox(user.id)
                return (
                    [r.occurrence_key for r in page1],
                    [r.occurrence_key for r in page2],
                    [r.occurrence_key for r in page3],
                    list(page4),
                    total,
                )
            finally:
                await session.rollback()

    p1, p2, p3, p4, total = _run(scenario())
    assert p1 == ["P4", "P3"]  # newest first
    assert p2 == ["P2", "P1"]
    assert p3 == ["P0"]
    assert p4 == []  # offset past the end -> empty page, no error
    assert total == 5


def test_live_rows_visible_orphans_and_dismissed_hidden_real_db():
    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            try:
                user = User(roll_number=_new_roll(), name="H4c Live vs Orphan")
                session.add(user)
                await session.flush()
                base = datetime.now(IST)

                live_event = AcademicEvent(
                    event_type=EventType.HOLIDAY,
                    start_date=date(2026, 10, 2),
                    end_date=date(2026, 10, 2),
                    active=True,
                )
                orphan_event = AcademicEvent(
                    event_type=EventType.HOLIDAY,
                    start_date=date(2026, 10, 3),
                    end_date=date(2026, 10, 3),
                    active=True,
                )
                session.add_all([live_event, orphan_event])
                await session.flush()

                # A plain live row (no event reference).
                session.add(_notification(user.id, key="live", created_at=base))
                # A live ACADEMIC_EVENT projection whose event still exists.
                session.add(_notification(
                    user.id, key="live_event", created_at=base + timedelta(minutes=1),
                    kind=NotificationKind.ACADEMIC_EVENT, event_id=live_event.id,
                ))
                # An orphaned ACADEMIC_EVENT projection: its event is deleted.
                session.add(_notification(
                    user.id, key="orphan", created_at=base + timedelta(minutes=2),
                    kind=NotificationKind.ACADEMIC_EVENT, event_id=orphan_event.id,
                ))
                # A dismissed row.
                session.add(_notification(
                    user.id, key="dismissed", created_at=base + timedelta(minutes=3),
                    is_dismissed=True,
                ))
                await session.flush()
                await session.delete(orphan_event)
                await session.flush()

                repo = NotificationRepository(session)
                keys = [r.occurrence_key for r in await repo.get_inbox(user.id, limit=200, offset=0)]
                unread = await repo.count_unread(user.id)
                total = await repo.count_inbox(user.id)
                return keys, unread, total
            finally:
                await session.rollback()

    keys, unread, total = _run(scenario())
    assert "live" in keys and "live_event" in keys          # live rows visible
    assert "orphan" not in keys                             # orphan never surfaces
    assert "dismissed" not in keys                          # dismissed hidden
    assert unread == 2                                      # orphan not in badge
    assert total == 2                                       # live non-dismissed only


def test_service_page_metadata_real_db():
    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            try:
                user = User(roll_number=_new_roll(), name="H4c Service Metadata")
                session.add(user)
                await session.flush()
                base = datetime.now(IST)
                for i in range(3):
                    session.add(_notification(
                        user.id, key=f"S{i}",
                        created_at=base + timedelta(minutes=i),
                        is_read=(i == 0),
                    ))
                await session.flush()

                svc = NotificationService(_RollbackSession(session))
                page = await svc.get_notifications(user, limit=2, offset=0)
                return page
            finally:
                await session.rollback()

    _notification_cache.clear()
    page = _run(scenario())
    assert [i.id for i in page.items] == ["MUST_ATTEND:S2", "MUST_ATTEND:S1"]
    assert page.limit == 2 and page.offset == 0
    assert page.total == 3 and page.has_more is True
    assert page.unread_count == 2  # S0 is read
    _notification_cache.clear()
