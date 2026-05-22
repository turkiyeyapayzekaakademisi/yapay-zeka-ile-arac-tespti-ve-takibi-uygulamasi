"""
Adımlar:
    1. Yeni Araç Oturumu oluştur
    2. Mevcut oturumu kapat
    3. Günlük istatistikleri getir
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.parking import VehicleSession
from app.schemas.schemas import DailyStatsResponse, VehicleSessionResponse

async def save_completed_sessions(db: AsyncSession, session_data: dict) -> VehicleSessionResponse:

    session = VehicleSession(
        vehicle_id = session_data["vehicle_id"],
        vehicle_type = session_data["vehicle_type"],
        entry_time = datetime.fromisoformat(session_data["entry_time"]),
        exit_time = datetime.fromisoformat(session_data["exit_time"]),
        duration_minutes = round(session_data["duration_minutes"], 2),
        fee = round(session_data["fee"], 2)
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def create_session(db: AsyncSession, vehicle_id: int, vehicle_type: str, entry_time: str) -> VehicleSession:

    session = VehicleSession(
        vehicle_id=vehicle_id,
        vehicle_type=vehicle_type,
        entry_time=datetime.fromisoformat(entry_time)
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def close_session(db:AsyncSession, vehicle_id: int, exit_time:str, duration_minutes: float, fee:float) -> VehicleSession | None:

    result = await db.execute(
        select(VehicleSession)
        .where(
            VehicleSession.vehicle_id == vehicle_id,
            VehicleSession.exit_time.is_(None),
        )
        .order_by(VehicleSession.entry_time.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if session is None:
        return None
    
    session.exit_time = datetime.fromisoformat(exit_time)
    session.duration_minutes = round(duration_minutes, 2)
    session.fee = round(fee, 2)

    await db.commit()
    await db.refresh(session)
    return session

async def get_daily_stats(
    db: AsyncSession,
    active_count: int,
) -> DailyStatsResponse:
    
    today_start = datetime.now(tz=timezone.utc).replace(
        hour = 0, minute = 0, second= 0, microsecond= 0
    )

    rows = await db.execute(
        select(VehicleSession)
        .where(
            VehicleSession.exit_time >= today_start,
            VehicleSession.exit_time.is_not(None)
        )
        .order_by(VehicleSession.exit_time.desc())
    )

    sessions = rows.scalars().all()

    earnings_result = await db.execute(
        select(func.coalesce(func.sum(VehicleSession.fee), 0.0))
        .where(
            VehicleSession.exit_time >= today_start,
            VehicleSession.exit_time.is_not(None)
        )
    )

    total_earnings = float(earnings_result.scalar())

    return DailyStatsResponse(
        date=datetime.now().date().isoformat(),
        total_earnings=round(total_earnings, 2),
        total_vehicles=len(sessions),
        active_vehicles=active_count,
        sessions=[VehicleSessionResponse.model_validate(s) for s in sessions]
    )