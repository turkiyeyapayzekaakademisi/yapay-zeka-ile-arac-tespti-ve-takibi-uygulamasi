import os
import requests

# API URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

def get_daily_stats() -> dict:

    response = requests.get(f"{API_BASE_URL}/parking/stats/daily", timeout=10)
    response.raise_for_status()
    return response.json()

def get_active_vehicles() -> dict:

    response = requests.get(f"{API_BASE_URL}/parking/stats/active", timeout=10)
    response.raise_for_status()
    return response.json()

def update_roi(gate_lines: list[list[int]], reverse_directions: list[bool]) -> dict:

    response = requests.post(
        f"{API_BASE_URL}/parking/config/roi",
        json={"gate_lines": gate_lines, "reverse_directions": reverse_directions},
        timeout= 10
    )
    response.raise_for_status()
    return response.json()

def update_pricing(hourly_rate: float) -> dict:

    response = requests.post(
        f"{API_BASE_URL}/parking/config/pricing",
        json={"hourly_rate": hourly_rate},
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def clear_database() -> dict:

    response = requests.delete(f"{API_BASE_URL}/parking/sessions/all", timeout=10)
    response.raise_for_status()
    return response.json()

def process_frame(image_bytes: bytes) -> tuple[bytes, list, int]:

    import json as _json

    response = requests.post(
        f"{API_BASE_URL}/parking/process/frame",
        files={"file": ("frame.jpg", image_bytes, "image/jpeg")},
        timeout=30
    )
    response.raise_for_status()

    try:
        events = _json.loads(response.headers.get("X-Events", "[]"))
    except _json.JSONDecodeError:
        events = []

    parked = int(response.headers.get("X-Parked", "0"))

    return response.content, events, parked