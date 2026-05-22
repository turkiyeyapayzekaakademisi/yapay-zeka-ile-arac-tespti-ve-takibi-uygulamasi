"""
Adımlar:
    1. OpenCV ile Video oku
    2. Yolo Modelini yükle ve nesne detectionı yap
    3. Araç Takibi ve ID ataması 
    4. ROI kullanarak belirli bir çizginin geçilip geçilmediğini kontrol et
    5. Otomatik park tespitinin yapılması

Kurulum
    1. requirements.txt dosyasına gerekli kütüphanelerin eklenmesi:
        ultralytics
        opencv-python-headless
    2. Bağımlılıkların yüklenmesi
    3. Çalıştırmanın yapılması
"""
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO

import logging
logger = logging.getLogger(__name__)


class ParkingDetector:

    VEHICLE_CLASSES  = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
    PARK_FRAMES      = 10
    PARK_MOVE_THRESH = 20
    ROI_MARGIN       = 200

    def __init__(self, model_path: str = "yolov8n.pt"):
        self.model = YOLO(model_path)

        self.prev_positions: dict[int, tuple[int, int]] = {}
        self.frame_count: int = 0

        self.gate_lines: list[tuple] = []
        self.reverse_gates: list[bool] = []
        self._roi_bbox: tuple | None = None

        self.tracked_vehicles: dict[int, dict] = {}
        self.pending_sessions: list[dict] = []

        self.pos_history: dict[int, deque] = {}
        self.parked_ids: set[int] = set()

    def process_frame(
        self,
        frame: np.ndarray,
        hourly_rate: float = 10.0,
    ) -> tuple[np.ndarray, list[dict]]:

        results = self.model.track(
            frame,
            persist=True,
            classes=list(self.VEHICLE_CLASSES.keys()),
        )

        events: list[dict] = []

        if results[0].boxes.id is None:
            self._draw_roi(frame)
            return frame, events

        boxes     = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.int().cpu().tolist()
        class_ids = results[0].boxes.cls.int().cpu().tolist()

        for box, track_id, class_id in zip(boxes, track_ids, class_ids):
            x1, y1, x2, y2 = map(int, box)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            v_type = self.VEHICLE_CLASSES.get(class_id, "vehicle")

            if not self._in_roi(cx, cy):
                continue

            prev = self.prev_positions.get(track_id)

            events += self._handle_gate_crossing(
                track_id, cx, cy, prev, v_type, hourly_rate
            )

            self._check_parking(track_id, cx, cy)

            color, label = self._box_style(track_id, v_type)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        self._update_tracking(boxes, track_ids)
        self._draw_roi(frame)

        cv2.putText(frame, f"Park: {len(self.parked_ids & set(track_ids))}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 100, 0), 2)

        return frame, events


    def _update_tracking(self, boxes: np.ndarray, track_ids: list[int]) -> None:
        self.frame_count += 1
        active = set(track_ids)
        for box, tid in zip(boxes, track_ids):
            bx1, by1, bx2, by2 = map(int, box)
            self.prev_positions[tid] = ((bx1 + bx2) // 2, (by1 + by2) // 2)
        self.prev_positions = {k: v for k, v in self.prev_positions.items() if k in active}
        self.pos_history    = {k: v for k, v in self.pos_history.items()    if k in active}
        self.parked_ids    &= active


    def set_gate_lines(
        self,
        gate_lines: list[tuple[int, int, int, int]],
        reverse_directions: list[bool] | None = None,
    ) -> None:
        self.gate_lines = list(gate_lines)
        n = len(gate_lines)
        if reverse_directions and len(reverse_directions) == n:
            self.reverse_gates = list(reverse_directions)
        else:
            self.reverse_gates = [False] * n
        self._roi_bbox = self._compute_roi_bbox()

    def _compute_roi_bbox(self) -> tuple | None:
        if not self.gate_lines:
            return None
        pts = [(x, y) for x1, y1, x2, y2 in self.gate_lines for x, y in ((x1, y1), (x2, y2))]
        m = self.ROI_MARGIN
        return (
            min(p[0] for p in pts) - m,
            min(p[1] for p in pts) - m,
            max(p[0] for p in pts) + m,
            max(p[1] for p in pts) + m,
        )

    def _in_roi(self, cx: int, cy: int) -> bool:
        if self._roi_bbox is None:
            return True
        x0, y0, x1, y1 = self._roi_bbox
        return x0 <= cx <= x1 and y0 <= cy <= y1

    def _draw_roi(self, frame: np.ndarray) -> None:
        if self._roi_bbox:
            x0, y0, x1, y1 = self._roi_bbox
            cv2.rectangle(frame, (max(0, x0), max(0, y0)), (x1, y1),
                          (80, 80, 80), 1, cv2.LINE_AA)
        for i, gate_line in enumerate(self.gate_lines):
            x1, y1, x2, y2 = gate_line
            cv2.line(frame, (x1, y1), (x2, y2), (255, 165, 0), 3)
            cv2.putText(frame, f"#{i+1}", (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            dx, dy = x2 - x1, y2 - y1
            length = max(1, int((dx**2 + dy**2) ** 0.5))
            nx, ny = -dy / length, dx / length
            if self.reverse_gates[i] if i < len(self.reverse_gates) else False:
                nx, ny = -nx, -ny
            a = 30
            ax, ay = int(mx + nx * a), int(my + ny * a)
            bx, by = int(mx - nx * a), int(my - ny * a)
            cv2.arrowedLine(frame, (mx, my), (ax, ay), (0, 220, 0), 2, tipLength=0.4)
            cv2.putText(frame, "G", (ax+4, ay+4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,220,0), 2)
            cv2.arrowedLine(frame, (mx, my), (bx, by), (0, 0, 220), 2, tipLength=0.4)
            cv2.putText(frame, "C", (bx+4, by+4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,220), 2)


    def _segment_crosses_line_direction(
        self,
        prev: tuple[int, int],
        curr: tuple[int, int],
        line: tuple[int, int, int, int],
    ) -> int:
        ax, ay = prev
        bx, by = curr
        cx_, cy_, dx, dy = line

        def _cross(ox, oy, ax_, ay_, bx_, by_):
            return (ax_ - ox) * (by_ - oy) - (ay_ - oy) * (bx_ - ox)

        d1 = _cross(cx_, cy_, dx, dy, ax, ay)
        d2 = _cross(cx_, cy_, dx, dy, bx, by)
        d3 = _cross(ax, ay, bx, by, cx_, cy_)
        d4 = _cross(ax, ay, bx, by, dx, dy)

        seg1 = (d1 >= 0 and d2 <= 0) or (d1 <= 0 and d2 >= 0)
        seg2 = (d3 >= 0 and d4 <= 0) or (d3 <= 0 and d4 >= 0)

        logger.debug(f"Segment Check → Prev:{prev} Curr:{curr} | D1:{d1} D2:{d2} | Cross:{seg1 and seg2}")

        if seg1 and seg2:
            if d1 <= 0 and d2 >= 0:
                return 1
            elif d1 >= 0 and d2 <= 0:
                return -1
        return 0

    def _handle_gate_crossing(
        self,
        track_id: int,
        cx: int,
        cy: int,
        prev: tuple | None,
        v_type: str,
        hourly_rate: float,
    ) -> list[dict]:
        events = []
        if not self.gate_lines or prev is None:
            return events

        for i, gate_line in enumerate(self.gate_lines):
            direction = self._segment_crosses_line_direction(prev, (cx, cy), gate_line)
            if direction == 0:
                continue
            rev = self.reverse_gates[i] if i < len(self.reverse_gates) else False
            logical_dir = -direction if rev else direction

            if logical_dir == 1 and track_id not in self.tracked_vehicles:
                self.tracked_vehicles[track_id] = {
                    "vehicle_id":   track_id,
                    "vehicle_type": v_type,
                    "entry_time":   datetime.now().isoformat(),
                    "entry_ts":     time.time(),
                    "entry_frame":  self.frame_count,
                }
                events.append({"event": "entry", "vehicle_id": track_id, "vehicle_type": v_type})
                logger.info(f"GIRIS → ID:{track_id}")

            elif logical_dir == -1 and track_id in self.tracked_vehicles:
                if self.frame_count - self.tracked_vehicles[track_id].get("entry_frame", self.frame_count) > 1:
                    session      = self.tracked_vehicles.pop(track_id)
                    duration_min = (time.time() - session["entry_ts"]) / 60
                    fee          = round((duration_min / 60) * hourly_rate, 2)
                    session.update({
                        "exit_time":        datetime.now().isoformat(),
                        "duration_minutes": round(duration_min, 2),
                        "fee":              fee,
                    })
                    self.pending_sessions.append(session)
                    events.append({"event": "exit", **session})
                    logger.info(f"CIKIS → ID:{track_id}  Süre:{duration_min:.1f}dk  Ücret:{fee}TL")
            break
        return events


    def _check_parking(self, track_id: int, cx: int, cy: int) -> None:
        hist = self.pos_history.setdefault(track_id, deque(maxlen=self.PARK_FRAMES))
        hist.append((cx, cy))
        if len(hist) >= self.PARK_FRAMES:
            xs = [p[0] for p in hist]
            ys = [p[1] for p in hist]
            if max(max(xs)-min(xs), max(ys)-min(ys)) < self.PARK_MOVE_THRESH:
                self.parked_ids.add(track_id)
            else:
                self.parked_ids.discard(track_id)

    def _box_style(self, track_id: int, v_type: str) -> tuple[tuple, str]:
        if track_id in self.parked_ids:
            return (255, 100, 0), f"ID:{track_id} PARK"
        if track_id in self.tracked_vehicles:
            return (0, 255, 0),   f"ID:{track_id} {v_type}"
        return     (0, 165, 255), f"ID:{track_id} {v_type}"

    def get_active_count(self) -> int:
        return len(self.tracked_vehicles)

    def get_parked_count(self) -> int:
        return len(self.parked_ids)

    def pop_pending_sessions(self) -> list[dict]:
        sessions = list(self.pending_sessions)
        self.pending_sessions.clear()
        return sessions


def run(source=0, gate_lines=None, reversed_dirs=None, save=False):

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"HATA: Kaynak açılamadı → {source}")
        return

    print("Genişlik :", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print("Yükseklik:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("FPS      :", cap.get(cv2.CAP_PROP_FPS))
    print("Kare sayı:", cap.get(cv2.CAP_PROP_FRAME_COUNT))

    detector = ParkingDetector()

    if gate_lines:
        n = len(gate_lines)
        revs = [(i in (reversed_dirs or [])) for i in range(n)]
        detector.set_gate_lines(gate_lines, revs)

    writer = None
    if save:
        w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        out_path = f"output_{datetime.now().strftime('%H%M%S')}.mp4"
        writer   = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        print(f"Kaydediliyor → {out_path}")

    paused = False

    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("p"):
            paused = not paused
        if key == ord("r"):
            detector.reverse_gates = [not r for r in detector.reverse_gates] or [True]
            detector._roi_bbox = detector._compute_roi_bbox()
        if paused:
            continue

        ret, frame = cap.read()
        if not ret:
            break

        out_frame, events = detector.process_frame(frame)

        for ev in events:
            print(f"  {'GİRİŞ' if ev['event'] == 'entry' else 'ÇIKIŞ'}"
                  f"  ID:{ev['vehicle_id']}  {ev['vehicle_type']}")

        cv2.imshow("detection_service", out_frame)

        if writer:
            writer.write(out_frame)

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print(f"\nİçeride: {detector.get_active_count()}  |  Park: {detector.get_parked_count()}")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ParkingDetector standalone test")
    parser.add_argument("--image",   help="Tek görsel dosyası (.jpg/.png)")
    parser.add_argument("--video",   help="Video dosyası (veya 0 webcam için)")
    parser.add_argument("--line",    action="append", metavar="x1,y1,x2,y2",
                        help="Kapı çizgisi (birden fazla kullanılabilir)")
    parser.add_argument("--reverse", action="append", type=int, metavar="N",
                        help="N. çizgiyi ters başlat (0=ilk, 1=ikinci)")
    parser.add_argument("--save",    action="store_true", help="Çıktıyı kaydet")
    args = parser.parse_args()

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"HATA: Görsel açılamadı → {args.image}")
            sys.exit(1)
        detector = ParkingDetector()
        result, _ = detector.process_frame(frame)
        if args.save:
            out = "output_" + args.image.split("/")[-1]
            cv2.imwrite(out, result)
            print(f"Kaydedildi → {out}")
        cv2.imshow("detection_service — q:cikis", result)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        sys.exit(0)

    gates = []
    for raw in (args.line or []):
        try:
            coords = tuple(int(v) for v in raw.split(","))
            assert len(coords) == 4
            gates.append(coords)
        except Exception:
            print(f"HATA: --line formatı x1,y1,x2,y2 olmalı → '{raw}'")
            sys.exit(1)

    source = 0 if args.video is None else (int(args.video) if args.video == "0" else args.video)
    run(source=source, gate_lines=gates or None, reversed_dirs=args.reverse, save=args.save)