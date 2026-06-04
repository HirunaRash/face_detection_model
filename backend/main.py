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

# ==========================================
# CONFIGURATION
# ==========================================
SUPABASE_URL = "https://pfexlwikctosunnulxkp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZXhsd2lrY3Rvc3VubnVseGtwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NjU3NzIsImV4cCI6MjA5NjA0MTc3Mn0.GqfBZSRBOPWh6oKUALXo2nvym9XkOZEmsK0VldeHzAA"
SUPABASE_BUCKET    = "face-signatures"
EMPLOYEES_TABLE    = "employees"
ATTENDANCE_TABLE   = "attendance_logs"

CAPTURE_TARGET     = 100          # face images captured per registration
CAPTURE_TIMEOUT    = 60           # max seconds to spend capturing (never gets stuck)
FACE_IMG_SIZE      = (160, 160)
STREAM_SCALE       = 0.5          # downscale for recognition speed
MATCH_TOLERANCE    = 0.5          # lower = stricter match
COOLDOWN_SECONDS   = 300          # minimum seconds between two logs for same person
HUD_COLOR          = (0, 230, 118)

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class RegisterRequest(BaseModel):
    name:  str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=100)

# ==========================================
# FASTAPI APP
# ==========================================
app = FastAPI(title="BioID Attendance API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# SUPABASE CLIENT
# ==========================================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# HAAR CASCADE
# ==========================================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
if face_cascade.empty():
    raise RuntimeError("Could not load Haar cascade XML.")

# ==========================================
# THREAD-SAFE GLOBALS
# ==========================================
_frame_lock      = threading.Lock()
_model_lock      = threading.RLock()
_attendance_lock = threading.Lock()
_sse_lock        = threading.Lock()

current_frame: Optional[np.ndarray] = None
server_alive   = True

known_encodings: List[np.ndarray] = []
known_ids:       List[int]         = []
id_to_name:      Dict[int, str]    = {}
id_to_title:     Dict[int, str]    = {}
last_logged:     Dict[int, float]  = {}

sse_clients: List[queue.Queue] = []

# ==========================================
# REGISTRATION STATUS (for progress SSE)
# ==========================================
reg_status: Dict = {"active": False, "captured": 0, "target": CAPTURE_TARGET, "done": False, "error": ""}
reg_lock = threading.Lock()

# ==========================================
# HELPERS
# ==========================================
def slugify(text: str) -> str:
    t = text.strip()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", "_", t)
    return t.strip("-_")

def face_area(loc: Tuple) -> int:
    top, right, bottom, left = loc
    return max(0, right - left) * max(0, bottom - top)

def decode_bytes(data: bytes) -> Optional[np.ndarray]:
    buf = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)

def broadcast(payload: dict) -> None:
    msg = json.dumps(payload)
    with _sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)

def clamp(box, fw, fh):
    x, y, w, h = box
    x = max(0, min(x, fw - 1))
    y = max(0, min(y, fh - 1))
    w = max(1, min(w, fw - x))
    h = max(1, min(h, fh - y))
    return x, y, w, h

# ==========================================
# CAMERA WORKER (background thread)
# ==========================================
def camera_worker():
    global current_frame, server_alive
    print("[Camera] Starting camera worker...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Camera] ERROR: Cannot open webcam.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
    print("[Camera] Webcam opened successfully.")
    while server_alive:
        ret, frame = cap.read()
        if ret and frame is not None:
            with _frame_lock:
                current_frame = frame
        else:
            time.sleep(0.005)
    cap.release()
    print("[Camera] Released webcam.")

# ==========================================
# MODEL SYNC  (load all employees from bucket)
# ==========================================
def sync_models() -> None:
    global known_encodings, known_ids, id_to_name, id_to_title
    print("[Sync] Syncing employee face models...")
    try:
        rows = supabase.table(EMPLOYEES_TABLE).select("id,name,title").execute().data or []
    except Exception as e:
        print(f"[Sync] DB fetch failed: {e}")
        return

    new_enc, new_ids, new_names, new_titles = [], [], {}, {}

    for emp in rows:
        eid   = int(emp["id"])
        ename = emp.get("name", "").strip()
        etitle= emp.get("title", "").strip()
        if not ename:
            continue
        new_names[eid]  = ename
        new_titles[eid] = etitle

        folder   = slugify(ename)
        bucket   = supabase.storage.from_(SUPABASE_BUCKET)
        encodings_for_emp = []

        for idx in range(1, CAPTURE_TARGET + 1):
            path = f"{folder}/face_{idx}.jpg"
            try:
                raw = bucket.download(path)
                if isinstance(raw, (bytearray, memoryview)):
                    raw = bytes(raw)
                img = decode_bytes(raw)
                if img is None:
                    continue
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb, model="hog")
                encs = face_recognition.face_encodings(rgb, locs)
                if encs:
                    encodings_for_emp.append(encs[0])
            except Exception:
                continue

        if encodings_for_emp:
            avg = np.mean(np.stack(encodings_for_emp, axis=0), axis=0)
            new_enc.append(avg)
            new_ids.append(eid)
            print(f"[Sync] Loaded {len(encodings_for_emp)} frames for '{ename}' (id={eid})")

    with _model_lock:
        known_encodings = new_enc
        known_ids       = new_ids
        id_to_name      = new_names
        id_to_title     = new_titles

    print(f"[Sync] Done. {len(new_enc)} employee(s) loaded.")

# ==========================================
# STARTUP / SHUTDOWN
# ==========================================
@app.on_event("startup")
def on_startup():
    threading.Thread(target=camera_worker, daemon=True).start()
    threading.Thread(target=sync_models,   daemon=True).start()

@app.on_event("shutdown")
def on_shutdown():
    global server_alive
    server_alive = False

# ==========================================
# ATTENDANCE LOGGING
# ==========================================
def log_attendance(emp_id: int) -> None:
    now = time.time()
    with _attendance_lock:
        if now - last_logged.get(emp_id, 0) < COOLDOWN_SECONDS:
            return
        last_logged[emp_id] = now

    name  = id_to_name.get(emp_id, "Unknown")
    title = id_to_title.get(emp_id, "")
    ts    = datetime.now().strftime("%I:%M:%S %p")

    def _insert():
        try:
            supabase.table(ATTENDANCE_TABLE).insert({"employee_id": emp_id}).execute()
        except Exception as e:
            print(f"[Attendance] Insert failed: {e}")
        broadcast({"name": name, "title": title, "time": ts})

    threading.Thread(target=_insert, daemon=True).start()

# ==========================================
# FACE MATCHING
# ==========================================
def match_face(encoding: np.ndarray) -> Tuple[Optional[int], float]:
    with _model_lock:
        encs = list(known_encodings)
        ids  = list(known_ids)
    if not encs:
        return None, 1.0
    dists   = face_recognition.face_distance(encs, encoding)
    matches = face_recognition.compare_faces(encs, encoding, tolerance=MATCH_TOLERANCE)
    hits    = [i for i, m in enumerate(matches) if m]
    if hits:
        best = min(hits, key=lambda i: dists[i])
        return ids[best], float(dists[best])
    return None, float(np.min(dists))

# ==========================================
# HUD DRAWING
# ==========================================
def draw_hud(frame, x, y, w, h, label, tick):
    c   = HUD_COLOR
    cl  = max(12, min(w, h) // 5)
    # corner brackets
    for (px, py, dx, dy) in [(x,y,1,0),(x,y,0,1),(x+w,y,-1,0),(x+w,y,0,1),
                              (x,y+h,1,0),(x,y+h,0,-1),(x+w,y+h,-1,0),(x+w,y+h,0,-1)]:
        cv2.line(frame, (px, py), (px + dx*cl, py + dy*cl), c, 2)
    # scan laser
    margin = max(6, h // 10)
    top_s, bot_s = y + margin, y + h - margin
    if bot_s > top_s:
        phase  = 0.5 + 0.5 * math.sin(tick * 0.1)
        scan_y = top_s + int((bot_s - top_s) * phase)
        cv2.line(frame, (x + 4, scan_y), (x + w - 4, scan_y), c, 1)
    # reticle
    cx, cy = x + w // 2, y + h // 2
    rs = max(5, min(w, h) // 10)
    cv2.circle(frame, (cx, cy), 2, c, -1)
    cv2.line(frame, (cx - rs, cy), (cx + rs, cy), c, 1)
    cv2.line(frame, (cx, cy - rs), (cx, cy + rs), c, 1)
    # label
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, label, (x, max(16, y - 10)), font, 0.45, c, 1, cv2.LINE_AA)
    cv2.putText(frame, f"X:{x} Y:{y}", (x, y + h + 16), font, 0.38, c, 1, cv2.LINE_AA)

# ==========================================
# MJPEG STREAM GENERATOR
# ==========================================
def frame_generator(recognition: bool = False) -> Generator[bytes, None, None]:
    box_hist: List[Tuple] = []
    last_box  = None
    last_label= "SCANNING..."
    missed    = 0
    tick      = 0

    while server_alive:
        with _frame_lock:
            frame = current_frame.copy() if current_frame is not None else None

        if frame is None:
            time.sleep(0.02)
            continue

        if recognition:
            small  = cv2.resize(frame, (0, 0), fx=STREAM_SCALE, fy=STREAM_SCALE)
            rgb_sm = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locs   = face_recognition.face_locations(rgb_sm, model="hog")
            encs   = face_recognition.face_encodings(rgb_sm, locs)

            new_box   = None
            new_label = "[ UNKNOWN ]"

            if locs and encs:
                best_loc = max(locs, key=face_area)
                idx      = locs.index(best_loc)
                emp_id, dist = match_face(encs[idx])

                if emp_id is not None:
                    name  = id_to_name.get(emp_id, "?")
                    title = id_to_title.get(emp_id, "")
                    new_label = f"[ {name} | {title} ]"
                    log_attendance(emp_id)

                top, right, bottom, left = best_loc
                sf = 1.0 / STREAM_SCALE
                bx = int(left * sf)
                by = int(top  * sf)
                bw = int((right - left) * sf)
                bh = int((bottom - top) * sf)
                new_box = clamp((bx, by, bw, bh), frame.shape[1], frame.shape[0])

            if new_box:
                box_hist.append(new_box)
                if len(box_hist) > 6:
                    box_hist.pop(0)
                xs = [b[0] for b in box_hist]
                ys = [b[1] for b in box_hist]
                ws = [b[2] for b in box_hist]
                hs = [b[3] for b in box_hist]
                last_box   = (int(np.mean(xs)), int(np.mean(ys)),
                               int(np.mean(ws)), int(np.mean(hs)))
                last_label = new_label
                missed     = 0
            else:
                missed += 1
                if missed > 20:
                    box_hist.clear()
                    last_box   = None
                    last_label = "SCANNING..."

            if last_box:
                x, y, w, h = clamp(last_box, frame.shape[1], frame.shape[0])
                draw_hud(frame, x, y, w, h, last_label, tick)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        tick += 1
        time.sleep(0.033)

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/stream/register")
def stream_register():
    """Plain camera stream for registration tab (no recognition overlay)."""
    return StreamingResponse(
        frame_generator(recognition=False),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@app.get("/api/stream/live")
def stream_live():
    """Camera stream WITH face recognition overlay for attendance tab."""
    return StreamingResponse(
        frame_generator(recognition=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@app.get("/api/attendance/events")
def attendance_events():
    """SSE endpoint — pushes attendance log entries to the frontend in real time."""
    client_q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        sse_clients.append(client_q)

    def event_stream():
        yield ": connected\n\n"
        try:
            while server_alive:
                try:
                    payload = client_q.get(timeout=15)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _sse_lock:
                if client_q in sse_clients:
                    sse_clients.remove(client_q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/api/registration/progress")
def registration_progress():
    """SSE endpoint — streams capture progress during employee registration."""
    def progress_stream():
        yield ": connected\n\n"
        while server_alive:
            with reg_lock:
                snap = dict(reg_status)
            yield f"data: {json.dumps(snap)}\n\n"
            if snap["done"] or snap["error"]:
                break
            time.sleep(0.3)

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/api/register")
def register_employee(payload: RegisterRequest, background_tasks: BackgroundTasks):
    """
    1. Insert employee record into DB
    2. Capture CAPTURE_TARGET face images from live camera
    3. Upload each image to Supabase Storage bucket
    4. Trigger model re-sync in background
    """
    global current_frame

    with _frame_lock:
        frame_check = current_frame

    if frame_check is None:
        raise HTTPException(503, "Camera feed not available. Please wait and try again.")

    clean_name  = payload.name.strip()
    clean_title = payload.title.strip()
    folder      = slugify(clean_name)

    # Insert into DB
    try:
        result = supabase.table(EMPLOYEES_TABLE).insert(
            {"name": clean_name, "title": clean_title}
        ).execute()
    except Exception as e:
        raise HTTPException(500, f"Database insert failed: {e}")

    rows = result.data or []
    if not rows:
        raise HTTPException(500, "No row returned after insert.")
    emp_id = int(rows[0]["id"])

    # Reset progress
    with reg_lock:
        reg_status.update({"active": True, "captured": 0,
                           "target": CAPTURE_TARGET, "done": False, "error": ""})

    bucket   = supabase.storage.from_(SUPABASE_BUCKET)
    captured: List[bytes] = []

    print(f"[Register] Capturing faces for '{clean_name}' (id={emp_id})...")

    # Detection stages: try strict first, fall back to looser if face is missed
    detect_stages = [
        {"scaleFactor": 1.1,  "minNeighbors": 4, "minSize": (50, 50)},
        {"scaleFactor": 1.1,  "minNeighbors": 3, "minSize": (40, 40)},
        {"scaleFactor": 1.05, "minNeighbors": 2, "minSize": (30, 30)},
    ]

    deadline = time.time() + CAPTURE_TIMEOUT

    while len(captured) < CAPTURE_TARGET and time.time() < deadline:
        with _frame_lock:
            frame = current_frame.copy() if current_frame is not None else None
        if frame is None:
            time.sleep(0.01)
            continue

        # Equalise histogram to handle dark/bright lighting
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Try each detection stage until a face is found
        faces = np.array([])
        for stage in detect_stages:
            faces = face_cascade.detectMultiScale(gray, **stage)
            if len(faces) > 0:
                break

        if len(faces) > 0:
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            fx, fy, fw, fh = clamp((fx, fy, fw, fh), frame.shape[1], frame.shape[0])
            crop = frame[fy: fy + fh, fx: fx + fw]
            if crop.size > 0:
                crop_resized = cv2.resize(crop, FACE_IMG_SIZE)
                ok, buf = cv2.imencode(".jpg", crop_resized,
                                       [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ok:
                    captured.append(buf.tobytes())
                    with reg_lock:
                        reg_status["captured"] = len(captured)

        time.sleep(0.01)

    print(f"[Register] Captured {len(captured)} face images in {CAPTURE_TIMEOUT - max(0.0, deadline - time.time()):.1f}s.")

    if len(captured) < 10:
        with reg_lock:
            reg_status.update({"active": False, "error": "No face detected during capture."})
        # Roll back DB insert
        try:
            supabase.table(EMPLOYEES_TABLE).delete().eq("id", emp_id).execute()
        except Exception:
            pass
        raise HTTPException(400, f"Only {len(captured)} face frames captured. Ensure your face is clearly visible and try again.")

    # Upload to Supabase Storage
    upload_ok = 0
    for i, img_bytes in enumerate(captured, start=1):
        path = f"{folder}/face_{i}.jpg"
        try:
            bucket.upload(path, img_bytes,
                          file_options={"content-type": "image/jpeg", "upsert": "true"})
            upload_ok += 1
        except Exception as e:
            print(f"[Register] Upload failed for {path}: {e}")

    print(f"[Register] Uploaded {upload_ok}/{len(captured)} images to bucket.")

    with reg_lock:
        reg_status.update({"active": False, "done": True, "captured": len(captured)})

    background_tasks.add_task(sync_models)
    return {
        "message":     "Registration successful",
        "employee_id": emp_id,
        "images_saved": upload_ok,
    }

@app.get("/api/employees")
def list_employees():
    """Return all registered employees."""
    try:
        rows = supabase.table(EMPLOYEES_TABLE).select("id,name,title").execute().data or []
        return {"employees": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    finally:
        server_alive = False