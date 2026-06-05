import re
import json
import queue
import threading
import time
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Generator

import numpy as np
import cv2
import face_recognition
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from supabase import Client, create_client

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SUPABASE_URL     = "https://pfexlwikctosunnulxkp.supabase.co"
SUPABASE_KEY     = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZXhsd2lrY3Rvc3VubnVseGtwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NjU3NzIsImV4cCI6MjA5NjA0MTc3Mn0.GqfBZSRBOPWh6oKUALXo2nvym9XkOZEmsK0VldeHzAA"
SUPABASE_BUCKET  = "face-signatures"
EMPLOYEES_TABLE  = "employees"
ATTENDANCE_TABLE = "attendance_logs"

CAPTURE_TARGET   = 100    # face images per registration
CAPTURE_TIMEOUT  = 90     # seconds max for capture loop
FACE_IMG_SIZE    = (160, 160)
STREAM_SCALE     = 0.75   # upsample before HOG — catches more faces
MATCH_TOLERANCE  = 0.55
CONFIRM_FRAMES   = 3      # consecutive matches before logging
COOLDOWN_SECS    = 300
HUD_GREEN        = (0, 230, 118)
HUD_GREY         = (80, 80, 80)

HAAR_STAGES = [
    {"scaleFactor": 1.1,  "minNeighbors": 4, "minSize": (50, 50)},
    {"scaleFactor": 1.1,  "minNeighbors": 3, "minSize": (40, 40)},
    {"scaleFactor": 1.05, "minNeighbors": 2, "minSize": (30, 30)},
]

# ─────────────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:  str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=100)

# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="BioID API", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
if face_cascade.empty():
    raise RuntimeError("Haar cascade not found.")

# ─────────────────────────────────────────────────────────────────────────────
# THREAD-SAFE GLOBALS
# ─────────────────────────────────────────────────────────────────────────────
_frame_lock  = threading.Lock()
_model_lock  = threading.RLock()
_attend_lock = threading.Lock()
_sse_lock    = threading.Lock()
_reg_lock    = threading.Lock()

current_frame:   Optional[np.ndarray] = None
server_alive     = True

known_encodings: List[np.ndarray] = []
known_ids:       List[int]        = []
id_to_name:      Dict[int, str]   = {}
id_to_title:     Dict[int, str]   = {}
last_logged:     Dict[int, float] = {}
sse_clients:     List[queue.Queue]= []

reg_status: Dict = {"active": False, "captured": 0,
                    "target": CAPTURE_TARGET, "done": False, "error": ""}

# ─────────────────────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────────────────────
def slugify(t: str) -> str:
    t = t.strip()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", "_", t)
    return t.strip("-_")

def face_area(loc: Tuple) -> int:
    top, right, bottom, left = loc
    return max(0, right - left) * max(0, bottom - top)

def decode_bytes(data: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def clamp(box: Tuple, fw: int, fh: int) -> Tuple:
    x, y, w, h = box
    x = max(0, min(x, fw - 1));  y = max(0, min(y, fh - 1))
    w = max(1, min(w, fw - x));  h = max(1, min(h, fh - y))
    return x, y, w, h

def broadcast(payload: dict) -> None:
    msg = json.dumps(payload)
    with _sse_lock:
        dead = []
        for q in sse_clients:
            try:    q.put_nowait(msg)
            except queue.Full: dead.append(q)
        for q in dead: sse_clients.remove(q)

def clahe_enhance(frame: np.ndarray) -> np.ndarray:
    """CLAHE on L-channel to fix dark / backlit faces."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    cl = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge([cl.apply(l), a, b]), cv2.COLOR_LAB2BGR)

# ─────────────────────────────────────────────────────────────────────────────
# CAMERA WORKER
# ─────────────────────────────────────────────────────────────────────────────
def camera_worker():
    global current_frame, server_alive
    print("[Cam] Opening webcam...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened(): cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Cam] ERROR: Cannot open webcam."); return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
    print("[Cam] Ready.")
    while server_alive:
        ret, frame = cap.read()
        if ret and frame is not None:
            with _frame_lock: current_frame = frame
        else:
            time.sleep(0.005)
    cap.release()
    print("[Cam] Released.")

# ─────────────────────────────────────────────────────────────────────────────
# MODEL SYNC
# CRITICAL FIX: saved images are already 160×160 face CROPS.
# We must NOT call face_locations() on them — HOG needs context/background.
# Instead pass the whole image rect as known_face_locations directly.
# ─────────────────────────────────────────────────────────────────────────────
def sync_models() -> None:
    global known_encodings, known_ids, id_to_name, id_to_title
    print("[Sync] Starting...")
    try:
        rows = supabase.table(EMPLOYEES_TABLE).select("id,name,title").execute().data or []
    except Exception as e:
        print(f"[Sync] DB error: {e}"); return

    new_enc: List[np.ndarray] = []
    new_ids: List[int]        = []
    new_names:  Dict[int, str]= {}
    new_titles: Dict[int, str]= {}

    for emp in rows:
        eid    = int(emp["id"])
        ename  = emp.get("name",  "").strip()
        etitle = emp.get("title", "").strip()
        if not ename: continue
        new_names[eid]  = ename
        new_titles[eid] = etitle

        folder = slugify(ename)
        bucket = supabase.storage.from_(SUPABASE_BUCKET)
        emp_encs: List[np.ndarray] = []

        # Sample every 5th image → up to 20 encodings per person (fast + representative)
        for idx in range(1, CAPTURE_TARGET + 1, 5):
            path = f"{folder}/face_{idx}.jpg"
            try:
                raw = bucket.download(path)
                if isinstance(raw, (bytearray, memoryview)): raw = bytes(raw)
                img = decode_bytes(raw)
                if img is None: continue

                # Upsample: dlib needs ≥ 80px to compute 128-d descriptor reliably
                img = cv2.resize(img, (200, 200))
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]

                # Pass entire image as the face region — skip re-detection on crops
                encs = face_recognition.face_encodings(
                    rgb,
                    known_face_locations=[(0, w, h, 0)],  # (top,right,bottom,left)
                    num_jitters=1
                )
                if encs: emp_encs.append(encs[0])
            except Exception as ex:
                print(f"[Sync] {path}: {ex}"); continue

        if emp_encs:
            for enc in emp_encs:
                new_enc.append(enc); new_ids.append(eid)
            print(f"[Sync] '{ename}': {len(emp_encs)} encodings loaded.")
        else:
            print(f"[Sync] WARNING: 0 encodings for '{ename}' (folder='{folder}')")

    with _model_lock:
        known_encodings = new_enc
        known_ids       = new_ids
        id_to_name      = new_names
        id_to_title     = new_titles

    print(f"[Sync] Done — {len(set(new_ids))} employee(s), {len(new_enc)} encoding(s) total.")

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP / SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    threading.Thread(target=camera_worker, daemon=True).start()
    threading.Thread(target=sync_models,   daemon=True).start()

@app.on_event("shutdown")
def on_shutdown():
    global server_alive
    server_alive = False

# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────────────────────────────────────────
def log_attendance(emp_id: int) -> None:
    now = time.time()
    with _attend_lock:
        if now - last_logged.get(emp_id, 0) < COOLDOWN_SECS: return
        last_logged[emp_id] = now
    name  = id_to_name.get(emp_id,  "Unknown")
    title = id_to_title.get(emp_id, "")
    ts    = datetime.now().strftime("%I:%M:%S %p")
    print(f"[Attendance] ✓ {name} at {ts}")
    def _insert():
        try: supabase.table(ATTENDANCE_TABLE).insert({"employee_id": emp_id}).execute()
        except Exception as e: print(f"[Attendance] DB error: {e}")
        broadcast({"name": name, "title": title, "time": ts})
    threading.Thread(target=_insert, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# FACE MATCHING
# ─────────────────────────────────────────────────────────────────────────────
def match_face(encoding: np.ndarray) -> Tuple[Optional[int], float]:
    with _model_lock:
        encs = list(known_encodings)
        ids  = list(known_ids)
    if not encs:
        print("[Match] No encodings loaded — call /api/sync"); return None, 1.0
    dists  = face_recognition.face_distance(encs, encoding)
    best_i = int(np.argmin(dists))
    best_d = float(dists[best_i])
    print(f"[Match] dist={best_d:.3f} threshold={MATCH_TOLERANCE}")
    if best_d <= MATCH_TOLERANCE:
        return ids[best_i], best_d
    return None, best_d

# ─────────────────────────────────────────────────────────────────────────────
# HUD DRAWING
# ─────────────────────────────────────────────────────────────────────────────
def draw_hud(frame, x, y, w, h, label, tick, matched: bool):
    c  = HUD_GREEN if matched else HUD_GREY
    cl = max(12, min(w, h) // 5)
    for px, py, dx, dy in [
        (x,   y,    1, 0),(x,   y,    0, 1),(x+w, y,   -1, 0),(x+w, y,    0, 1),
        (x,   y+h,  1, 0),(x,   y+h,  0,-1),(x+w, y+h, -1, 0),(x+w, y+h,  0,-1),
    ]:
        cv2.line(frame, (px, py), (px+dx*cl, py+dy*cl), c, 2)
    m = max(6, h//10); ts_y, bs_y = y+m, y+h-m
    if bs_y > ts_y:
        sy = ts_y + int((bs_y - ts_y) * (0.5 + 0.5 * math.sin(tick * 0.1)))
        cv2.line(frame, (x+4, sy), (x+w-4, sy), c, 1)
    cx, cy = x+w//2, y+h//2; rs = max(5, min(w, h)//10)
    cv2.circle(frame, (cx, cy), 2, c, -1)
    cv2.line(frame, (cx-rs, cy), (cx+rs, cy), c, 1)
    cv2.line(frame, (cx, cy-rs), (cx, cy+rs), c, 1)
    cv2.putText(frame, label, (x, max(16, y-10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1, cv2.LINE_AA)

# ─────────────────────────────────────────────────────────────────────────────
# STREAM GENERATOR
# FIX: wrapped in try/except GeneratorExit so cleanup happens when
#      the browser disconnects (tab switch / refresh).
# ─────────────────────────────────────────────────────────────────────────────
def frame_generator(recognition: bool = False) -> Generator[bytes, None, None]:
    box_hist:     List[Tuple]    = []
    last_box:     Optional[Tuple]= None
    last_label    = "SCANNING..."
    last_matched  = False
    missed        = 0
    tick          = 0
    confirm_id:   Optional[int]  = None
    confirm_count = 0

    try:
        while server_alive:
            with _frame_lock:
                raw = current_frame.copy() if current_frame is not None else None
            if raw is None:
                time.sleep(0.02); continue

            frame = raw.copy()

            if recognition:
                # ── CLAHE enhance → scale up → HOG detect ──────────────────
                enhanced = clahe_enhance(raw)
                small    = cv2.resize(enhanced, (0, 0), fx=STREAM_SCALE, fy=STREAM_SCALE)
                rgb_sm   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                locs = face_recognition.face_locations(rgb_sm, model="hog")
                encs = face_recognition.face_encodings(rgb_sm, locs)

                new_box = None; new_label = "[ UNKNOWN ]"; new_matched = False

                if locs and encs:
                    best_loc = max(locs, key=face_area)
                    idx      = locs.index(best_loc)
                    emp_id, dist = match_face(encs[idx])

                    if emp_id is not None:
                        name  = id_to_name.get(emp_id, "?")
                        title = id_to_title.get(emp_id, "")
                        new_label   = f"[ {name} | {title} ]"
                        new_matched = True
                        if emp_id == confirm_id: confirm_count += 1
                        else: confirm_id = emp_id; confirm_count = 1
                        if confirm_count >= CONFIRM_FRAMES:
                            log_attendance(emp_id)
                    else:
                        confirm_id = None; confirm_count = 0

                    top, right, bottom, left = best_loc
                    sf = 1.0 / STREAM_SCALE
                    new_box = clamp(
                        (int(left*sf), int(top*sf),
                         int((right-left)*sf), int((bottom-top)*sf)),
                        frame.shape[1], frame.shape[0])

                if new_box:
                    box_hist.append(new_box)
                    if len(box_hist) > 6: box_hist.pop(0)
                    last_box = tuple(int(np.mean([b[i] for b in box_hist]))
                                     for i in range(4))
                    last_label = new_label; last_matched = new_matched; missed = 0
                else:
                    missed += 1
                    if missed > 25:
                        box_hist.clear(); last_box = None
                        last_label = "SCANNING..."; last_matched = False
                        confirm_id = None; confirm_count = 0

                if last_box:
                    x, y, w, h = clamp(last_box, frame.shape[1], frame.shape[0])
                    draw_hud(frame, x, y, w, h, last_label, tick, last_matched)

            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + buf.tobytes() + b"\r\n")
            tick += 1
            time.sleep(0.033)

    except GeneratorExit:
        print(f"[Stream] Client disconnected ({'live' if recognition else 'register'}).")

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/stream/register")
def stream_register():
    return StreamingResponse(
        frame_generator(recognition=False),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/stream/live")
def stream_live():
    return StreamingResponse(
        frame_generator(recognition=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/attendance/events")
def attendance_events():
    client_q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock: sse_clients.append(client_q)
    def event_stream():
        yield ": connected\n\n"
        try:
            while server_alive:
                try:    yield f"data: {client_q.get(timeout=15)}\n\n"
                except queue.Empty: yield ": ping\n\n"
        finally:
            with _sse_lock:
                if client_q in sse_clients: sse_clients.remove(client_q)
    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/registration/progress")
def registration_progress():
    def stream():
        yield ": connected\n\n"
        while server_alive:
            with _reg_lock: snap = dict(reg_status)
            yield f"data: {json.dumps(snap)}\n\n"
            if snap["done"] or snap["error"]: break
            time.sleep(0.3)
    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/register")
def register_employee(payload: RegisterRequest, background_tasks: BackgroundTasks):
    with _frame_lock:
        if current_frame is None:
            raise HTTPException(503, "Camera not ready.")
    clean_name  = payload.name.strip()
    clean_title = payload.title.strip()
    folder      = slugify(clean_name)
    try:
        result = supabase.table(EMPLOYEES_TABLE).insert(
            {"name": clean_name, "title": clean_title}).execute()
    except Exception as e:
        raise HTTPException(500, f"DB insert failed: {e}")
    rows = result.data or []
    if not rows: raise HTTPException(500, "No row returned after insert.")
    emp_id = int(rows[0]["id"])
    with _reg_lock:
        reg_status.update({"active": True, "captured": 0,
                           "target": CAPTURE_TARGET, "done": False, "error": ""})
    bucket   = supabase.storage.from_(SUPABASE_BUCKET)
    captured: List[bytes] = []
    deadline = time.time() + CAPTURE_TIMEOUT
    print(f"[Register] Capturing for '{clean_name}' id={emp_id}...")
    while len(captured) < CAPTURE_TARGET and time.time() < deadline:
        with _frame_lock:
            frame = current_frame.copy() if current_frame is not None else None
        if frame is None: time.sleep(0.01); continue
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        faces = np.array([])
        for stage in HAAR_STAGES:
            faces = face_cascade.detectMultiScale(gray, **stage)
            if len(faces) > 0: break
        if len(faces) > 0:
            fx, fy, fw, fh = max(faces, key=lambda f: f[2]*f[3])
            fx, fy, fw, fh = clamp((fx, fy, fw, fh), frame.shape[1], frame.shape[0])
            crop = frame[fy:fy+fh, fx:fx+fw]
            if crop.size > 0:
                ok, buf = cv2.imencode(".jpg", cv2.resize(crop, FACE_IMG_SIZE),
                                       [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ok:
                    captured.append(buf.tobytes())
                    with _reg_lock: reg_status["captured"] = len(captured)
        time.sleep(0.01)
    print(f"[Register] Captured {len(captured)} images.")
    if len(captured) < 10:
        with _reg_lock: reg_status.update({"active": False, "error": "Too few frames."})
        try: supabase.table(EMPLOYEES_TABLE).delete().eq("id", emp_id).execute()
        except Exception: pass
        raise HTTPException(400, f"Only {len(captured)} frames — keep face visible and retry.")
    upload_ok = 0
    for i, img_bytes in enumerate(captured, start=1):
        try:
            bucket.upload(f"{folder}/face_{i}.jpg", img_bytes,
                          file_options={"content-type": "image/jpeg", "upsert": "true"})
            upload_ok += 1
        except Exception as e: print(f"[Register] Upload {i} failed: {e}")
    print(f"[Register] Uploaded {upload_ok}/{len(captured)}.")
    with _reg_lock: reg_status.update({"active": False, "done": True, "captured": len(captured)})
    background_tasks.add_task(sync_models)
    return {"message": "Registration successful",
            "employee_id": emp_id, "images_saved": upload_ok}

@app.get("/api/employees")
def list_employees():
    try:
        rows = supabase.table(EMPLOYEES_TABLE).select("id,name,title").execute().data or []
        return {"employees": rows}
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/api/sync")
def manual_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_models)
    return {"message": "Sync triggered"}

@app.get("/api/debug/encodings")
def debug_encodings():
    with _model_lock:
        count = len(known_encodings); ids = list(set(known_ids))
    return {"total_encodings": count, "employee_ids": ids,
            "names": {eid: id_to_name.get(eid) for eid in ids}}

if __name__ == "__main__":
    import uvicorn
    try: uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    finally: server_alive = False