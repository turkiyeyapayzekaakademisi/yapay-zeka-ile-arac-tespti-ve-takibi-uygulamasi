from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VehicleSessionResponse(BaseModel):

    id: int
    vehicle_id: int
    vehicle_type: str
    entry_time: datetime
    exit_time: Optional[datetime]
    duration_minutes: Optional[float]
    fee: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True

class DailyStatsResponse(BaseModel):

    date: str
    total_earnings: float
    total_vehicles: int
    active_vehicles: int
    sessions: list[VehicleSessionResponse]

class ROIConfigRequest(BaseModel):
    
    gate_lines: list[tuple[int, int, int, int]]
    reverse_directions: list[bool] = []

class PricingConfigRequest(BaseModel):

    hourly_rate: float = 10.0

class FrameEventResponse(BaseModel):

    event: str
    vehicle_id: int
    vehicle_type: str