import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import parking as parking_router
from app.core.config import settings
from app.db.database import engine, init_db
from app.services.detection_service import ParkingDetector


@asynccontextmanager
async def lifespan(app: FastAPI):

    await init_db()
    print("DB Başlatıldı")

    detector = ParkingDetector()
    parking_router.set_detector(detector)
    parking_router.set_hourly_rate(settings.HOURLY_RATE)
    print("Parking Detector başarıyla başlatıldı")

    yield
    print("Uygulama kapatıldı")


app = FastAPI(
    title = "Yapay Zeka ile Araç Tespiti ve Takibi Uygulaması",
    description="Yolo tabanlı araç tespiti ve takibi uygulaması",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_orgins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(parking_router.router, prefix="/api/v1/parking", tags=["Parking"])

@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "Uygulama çalışıyor."}