"""READ-ONLY notification-forensics queries (discovery only, no writes)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

Q = {
    "notif_event_refs_missing": """
        SELECT count(*) FROM notifications n
        WHERE n.kind = 'ACADEMIC_EVENT'
          AND NOT EXISTS (SELECT 1 FROM academic_events e WHERE e.id = n.event_id)
    """,
    "notif_event_refs_inactive": """
        SELECT count(*) FROM notifications n
        WHERE n.kind = 'ACADEMIC_EVENT' AND n.event_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM academic_events e WHERE e.id = n.event_id AND NOT e.active)
    """,
    "notif_per_user": """
        SELECT u.roll_number, n.kind, count(*),
               count(*) FILTER (WHERE NOT n.is_read) unread
        FROM notifications n JOIN users u ON u.id = n.user_id
        GROUP BY 1,2 ORDER BY 1,2
    """,
    "notif_session_refs_missing": """
        SELECT count(*) FROM notifications n
        WHERE n.kind = 'CLASS_REMINDER' AND n.session_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM class_sessions c WHERE c.id = n.session_id)
    """,
    "oldest_notification": "SELECT min(created_at), max(created_at) FROM notifications",
    "unread_total": "SELECT count(*) FROM notifications WHERE NOT is_read AND NOT is_dismissed",
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for name, sql in Q.items():
            print(f"\n=== {name} ===")
            result = await db.execute(text(sql))
            for r in result.fetchall():
                print("  " + " | ".join("" if v is None else str(v) for v in r))
    print("\nDONE (read-only).")


if __name__ == "__main__":
    asyncio.run(main())
