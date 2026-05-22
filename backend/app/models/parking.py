from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.db.database import Base


class VehicleSession(Base):

    __tablename__ = "vehicle_sessions"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    vehicle_type = Column(String(20), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Float, nullable=True)
    fee = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )