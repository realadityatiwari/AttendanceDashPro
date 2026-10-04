"""E-1 regression: /attendance/summary defaults to the INSTITUTION-local today.

The 2026-10 audit found the endpoint defaulting ``as_of_date`` with the
server-local ``date.today()`` while every other student-facing surface uses
the canonical ``institution_today()`` (Asia/Kolkata) — on a UTC host between
00:00-05:30 IST the two disagree, silently shifting the summary's count
horizon (and its optimizer's pending set) by one day.

DB-free regression: the endpoint's collaborators are replaced with fakes and
the endpoint coroutine is called directly. A patched ``institution_today`` in
the endpoint's namespace proves the default flows from the CANONICAL helper
(not ``date.today()``); an explicit ``as_of_date`` must pass through verbatim.
A static tripwire keeps the old ``else date.today()`` default out.
"""

import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.endpoints import attendance as attendance_endpoint

SUBJECT_ID = uuid4()
INSTITUTION_TODAY = date(2026, 10, 4)  # IST date a UTC server might not agree with


class _FakeSubjectRepo:
    def __init__(self, db):
        pass

    async def get_by_code(self, code):
        return SimpleNamespace(id=SUBJECT_ID, code=code)


class _FakeAttendanceRepo:
    def __init__(self, db):
        pass

    async def is_enrolled(self, user_id, subject_id):
        return True


class _FakeService:
    received = {}

    def __init__(self, db):
        pass

    async def get_summary(self, user_id, subject_id, subject_code, as_of_date):
        _FakeService.received = {
            "user_id": user_id,
            "subject_id": subject_id,
            "subject_code": subject_code,
            "as_of_date": as_of_date,
        }
        return SimpleNamespace(subject_code=subject_code)


def _patch(monkeypatch):
    monkeypatch.setattr(attendance_endpoint, "SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr(attendance_endpoint, "AttendanceRepository", _FakeAttendanceRepo)
    monkeypatch.setattr(attendance_endpoint, "AttendanceService", _FakeService)
    monkeypatch.setattr(attendance_endpoint, "institution_today", lambda: INSTITUTION_TODAY)


async def _call(as_of_date):
    return await attendance_endpoint.get_attendance_summary(
        subject_code="BCS-501",
        as_of_date=as_of_date,
        current_user=SimpleNamespace(id=uuid4()),
        db=None,
    )


def test_omitted_as_of_date_defaults_to_institution_local_today(monkeypatch):
    _patch(monkeypatch)
    asyncio.run(_call(None))
    assert _FakeService.received["as_of_date"] == INSTITUTION_TODAY


def test_explicit_as_of_date_passes_through_unchanged(monkeypatch):
    _patch(monkeypatch)
    asyncio.run(_call(date(2026, 1, 15)))
    assert _FakeService.received["as_of_date"] == date(2026, 1, 15)


def test_endpoint_default_never_uses_server_local_date_today():
    # Static tripwire: the old default pattern must not return.
    source = attendance_endpoint.__file__
    text = open(source, encoding="utf-8").read()
    assert "else date.today()" not in text
