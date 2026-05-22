import json

import cv2
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import (
    DailyStatsResponse,
    ROIConfigRequest,
    PricingConfigRequest
)

from app.services import parking_service

router = APIRouter()

_detector = None
_hourly_rate: float = 10.0

def set_detector(detector):
    global _detector
    _detector = detector

def set_hourly_rate(rate: float):
    global _hourly_rate
    _hourly_rate = rate

@router.get("/stats/daily", response_model=DailyStatsResponse)
async def daily_stats(db: AsyncSession = Depends(get_db)):

    active = _detector.get_active_count() if _detector else 0
    return await parking_service.get_daily_stats(db, active_count=active)

@router.get("/stats/active")
async def active_vehicles():

    if _detector is None:
        return {"count": 0, "vehicles": []}
    return {
        "count": _detector.get_active_count(),
        "vehicles": list(_detector.tracked_vehicles.values()),
    }

@router.post("/config/roi")
async def set_roi(config: ROIConfigRequest):

    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector henüz başlatılmadı.")
    _detector.set_gate_lines(config.gate_lines, config.reverse_directions)
    return {"message": f"{len(config.gate_lines)} kapı çizgisi güncellendi"}

@router.post("/config/pricing")
async def set_pricing(config: PricingConfigRequest):

    set_hourly_rate(config.hourly_rate)
    return{"message": f"Saatlik ücret {config.hourly_rate} TL olarak güncellendi"}

@router.post("/process/frame")
async def process_frame(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    
    if _detector is None:
        raise HTTPException(status_code=503, detail="Detector henüz başlatılmadı")
    
    contents = await file.read()
    arr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Geçersiz görüntü dosyası")
    
    processed_frame, events = _detector.process_frame(frame, _hourly_rate)

    for session_data in _detector.pop_pending_sessions():
        await parking_service.save_completed_sessions(db, session_data)

    _, buffer = cv2.imencode(".jpg", processed_frame)

    return StreamingResponse(
        iter([buffer.tobytes()]),
        media_type="image/jpeg",
        headers={
            "X-Events": json.dumps(events, ensure_ascii=False),
            "X-Parked": str(_detector.get_parked_count())
        }
    )

@router.delete("/sessions/all")
async def clear_all_sessions(db: AsyncSession = Depends(get_db)):

    from sqlalchemy import delete
    from app.models.parking import VehicleSession

    await db.execute(delete(VehicleSession))
    await db.commit()

    if _detector:
        _detector.tracked_vehicles.clear()
        _detector.pending_sessions.clear()
        _detector.parked_ids.clear()
        _detector.pos_history.clear()
        _detector.prev_positions.clear()

    return {"message": "Tüm oturumlar silindi"}

@router.get("/sessions")
async def get_sessions(
    skip: int = Query(default=0, ge=0, description="Atlanacak kayıt sayısı"),
    limit: int = Query(default=50, ge=1, le=200, description="Döndürlecek maksimum kayıt sayısı"),
    db: AsyncSession = Depends(get_db)
):
    
    from sqlalchemy import select
    from app.models.parking import VehicleSession
    from app.schemas.schemas import VehicleSessionResponse

    rows = await db.execute(
        select(VehicleSession)
        .order_by(VehicleSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    sessions = rows.scalars().all()
    return {"sessions": [VehicleSessionResponse.model_validate(s) for s in sessions]}