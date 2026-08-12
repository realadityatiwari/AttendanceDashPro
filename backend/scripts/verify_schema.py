import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def verify_thresholds():
    engine = create_async_engine(settings.DATABASE_URI)
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT q.cycle_number, q.label, p.lecture_threshold 
            FROM quiz_cycles q
            JOIN eligibility_policies p ON p.quiz_cycle_id = q.id
            ORDER BY q.cycle_number
        """))
        for row in result:
            print(f"Cycle {row[0]} ({row[1]}): {row[2]}%")
            
        print("\nVerifying BCS-054 schedules:")
        result = await conn.execute(text("""
            SELECT q.cycle_number, s.date, s.schedule_status 
            FROM quiz_schedules s
            JOIN quiz_cycles q ON s.quiz_cycle_id = q.id
            JOIN subjects sub ON s.subject_id = sub.id
            WHERE sub.code = 'BCS-054'
            ORDER BY q.cycle_number
        """))
        for r in result:
            print(f"BCS-054 Cycle {r[0]}: date={r[1]}, status={r[2]}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_thresholds())
