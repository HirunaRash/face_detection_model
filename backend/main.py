import os
import re
import threading
import time
import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import cv2
import face_recognition
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from supabase import Client, create_client

SUPABASE_URL = "https://pfexlwikctosunnulxkp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZXhsd2lrY3Rvc3VubnVseGtwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NjU3NzIsImV4cCI6MjA5NjA0MTc3Mn0.GqfBZSRBOPWh6oKUALXo2nvym9XkOZEmsK0VldeHzAA"
SUPABASE_BUCKET = "face-signatures"
DATABASE_TABLE = "employees"
ATTENDANCE_TABLE = "attendance_logs"
ATTENDANCE_COOLDOWN_SECONDS = 300
FACE_IMAGE_SIZE = (200, 200)
STREAM_SCALE = 0.5
FACE_MATCH_TOLERANCE = 0.6  
HUD_COLOR = (255, 191, 0)

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=100)

app = FastAPI(title="Face Recognition Attendance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()

model_lock = threading.RLock()
camera_lock = threading.RLock()
attendance_lock = threading.RLock()

# Shared background stream container to solve the hardware resource locking conflict
current_live_frame: Optional[np.ndarray] = None

last_logged_time: Dict[int, float] = {}
id_to_name: Dict[int, str] = {}
id_to_title: Dict[int, str] = {}
known_face_encodings: List[np.ndarray] = []
known_face_ids: List[int] = []

if face_cascade.empty():
    raise RuntimeError("Failed to load Haar cascade face detector.")

def clean_text(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"[<>:\"/\\|?*]+", "_", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned.strip("._ ")

def clean_display_text(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

def choose_largest_face(faces: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    if len(faces) == 0:
        return None
    return max(faces, key=lambda face: face[2] * face[3])

def face_location_area(location: Tuple[int, int, int, int]) -> int:
    top, right, bottom, left = location
    return max(0, right - left) * max(0, bottom - top)

def decode_image_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    if not image_bytes:
        return None
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)

def extract_face_crop_and_encoding(image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(image_rgb, model="hog")
    if not face_locations:
        return None, None

    selected_location = max(face_locations, key=face_location_area)
    encodings = face_recognition.face_encodings(image_rgb, known_face_locations=[selected_location])
    if not encodings:
        return None, None

    top, right, bottom, left = selected_location
    gray_image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    face_crop = gray_image[top:bottom, left:right]
    if face_crop.size == 0:
        return None, None

    face_crop = cv2.resize(face_crop, FACE_IMAGE_SIZE)
    return face_crop, encodings[0]

def load_face_profile_from_bucket(employee_id: int, employee_name: str) -> Tuple[List[np.ndarray], List[np.ndarray]]:
    bucket = supabase.storage.from_(SUPABASE_BUCKET)
    folder_name = clean_text(employee_name)

    lbph_samples: List[np.ndarray] = []
    face_encodings: List[np.ndarray] = []

    for index in range(1, 15): 
        object_path = f"{folder_name}/face_{index}.jpg"
        try:
            image_bytes = bucket.download(object_path)
        except Exception:
            continue

        if isinstance(image_bytes, (bytearray, memoryview)):
            image_bytes = bytes(image_bytes)

        image_bgr = decode_image_bytes(image_bytes)
        if image_bgr is None:
            continue

        face_crop, face_encoding = extract_face_crop_and_encoding(image_bgr)
        if face_crop is not None:
            lbph_samples.append(face_crop)
        if face_encoding is not None:
            face_encodings.append(face_encoding)

    return lbph_samples, face_encodings

def sync_employee_models() -> None:
    global lbph_recognizer, id_to_name, id_to_title, known_face_encodings, known_face_ids
    print("Starting background employee model synchronization...")
    try:
        response = supabase.table(DATABASE_TABLE).select("id,name,title").execute()
        employees = response.data or []
    except Exception as e:
        print(f"Failed to fetch dataset from Supabase on launch: {e}")
        return

    if not employees:
        print("No registered employees found.")
        with model_lock:
            id_to_name = {}
            id_to_title = {}
            known_face_encodings = []
            known_face_ids = []
        return

    new_id_to_name: Dict[int, str] = {}
    new_id_to_title: Dict[int, str] = {}
    training_images: List[np.ndarray] = []
    training_labels: List[int] = []
    profile_encodings: List[np.ndarray] = []
    profile_ids: List[int] = []

    for employee in employees:
        employee_id = int(employee["id"])
        employee_name = clean_display_text(str(employee.get("name", "")))
        employee_title = clean_display_text(str(employee.get("title", "")))

        if not employee_name:
            continue

        new_id_to_name[employee_id] = employee_name
        new_id_to_title[employee_id] = employee_title

        lbph_samples, face_encodings = load_face_profile_from_bucket(employee_id, employee_name)
        for sample in lbph_samples:
            training_images.append(sample)
            training_labels.append(employee_id)
        if face_encodings:
            averaged_encoding = np.mean(np.stack(face_encodings, axis=0), axis=0)
            profile_encodings.append(averaged_encoding)
            profile_ids.append(employee_id)

    with model_lock:
        id_to_name = new_id_to_name
        id_to_title = new_id_to_title
        known_face_encodings = profile_encodings
        known_face_ids = profile_ids
        lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
        if training_images:
            lbph_recognizer.train(training_images, np.array(training_labels, dtype=np.int32))
    print("Employee models successfully synced.")

@app.on_event("startup")
def on_startup() -> None:
    threading.Thread(target=sync_employee_models, daemon=True).start()

def build_employee_display_name(employee_id: int) -> str:
    name = id_to_name.get(employee_id, "").strip()
    title = id_to_title.get(employee_id, "").strip()
    if title and name:
        return f"Hi {title} - {name}"
    if name:
        return f"Hi {name}"
    return f"Hi Employee {employee_id}"

def queue_attendance_log(employee_id: int) -> None:
    now = time.time()
    with attendance_lock:
        last_time = last_logged_time.get(employee_id, 0.0)
        if now - last_time < ATTENDANCE_COOLDOWN_SECONDS:
            return
        last_logged_time[employee_id] = now

    def _insert_log() -> None:
        try:
            supabase.table(ATTENDANCE_TABLE).insert({"employee_id": employee_id}).execute()
        except Exception as exc:
            print(f"Attendance insert failed for employee {employee_id}: {exc}")

    threading.Thread(target=_insert_log, daemon=True).start()

def match_employee(face_encoding: np.ndarray) -> Tuple[Optional[int], bool, float]:
    with model_lock:
        local_encodings = list(known_face_encodings)
        local_ids = list(known_face_ids)

    if not local_encodings:
        return None, False, 1.0

    distances = face_recognition.face_distance(local_encodings, face_encoding)
    matches = face_recognition.compare_faces(local_encodings, face_encoding, tolerance=FACE_MATCH_TOLERANCE)

    matched_indexes = [index for index, matched in enumerate(matches) if matched]
    if matched_indexes:
        best_index = min(matched_indexes, key=lambda index: distances[index])
        best_distance = float(distances[best_index])
        return local_ids[best_index], True, best_distance

    if len(distances) > 0:
        best_index = int(np.argmin(distances))
        return None, False, float(distances[best_index])
    return None, False, 1.0

def clamp_box(box: Tuple[int, int, int, int], frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
    x, y, w, h = box
    x = max(0, min(x, frame_width - 1))
    y = max(0, min(y, frame_height - 1))
    w = max(1, min(w, frame_width - x))
    h = max(1, min(h, frame_height - y))
    return x, y, w, h

def location_to_box(location: Tuple[int, int, int, int], scale_factor: float) -> Tuple[int, int, int, int]:
    top, right, bottom, left = location
    x = int(round(left * scale_factor))
    y = int(round(top * scale_factor))
    w = int(round((right - left) * scale_factor))
    h = int(round((bottom - top) * scale_factor))
    return x, y, w, h

def average_box_history(box_history: List[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    if not box_history:
        return None
    x_mean = int(round(np.mean([box[0] for box in box_history])))
    y_mean = int(round(np.mean([box[1] for box in box_history])))
    w_mean = int(round(np.mean([box[2] for box in box_history])))
    h_mean = int(round(np.mean([box[3] for box in box_history])))
    return x_mean, y_mean, w_mean, h_mean

def draw_corner_brackets(frame: np.ndarray, x: int, y: int, w: int, h: int, color=HUD_COLOR, thickness: int = 2) -> None:
    corner_length = max(12, min(w, h) // 5)
    cv2.line(frame, (x, y), (x + corner_length, y), color, thickness)
    cv2.line(frame, (x, y), (x, y + corner_length), color, thickness)
    cv2.line(frame, (x + w, y), (x + w - corner_length, y), color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + corner_length), color, thickness)
    cv2.line(frame, (x, y + h), (x + corner_length, y + h), color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - corner_length), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w - corner_length, y + h), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - corner_length), color, thickness)

def draw_reticle(frame: np.ndarray, x: int, y: int, w: int, h: int, color=HUD_COLOR) -> None:
    center_x = x + w // 2
    center_y = y + h // 2
    reticle_size = max(4, min(w, h) // 12)
    cv2.circle(frame, (center_x, center_y), 2, color, -1)
    cv2.line(frame, (center_x - reticle_size, center_y), (center_x + reticle_size, center_y), color, 1)
    cv2.line(frame, (center_x, center_y - reticle_size), (center_x, center_y + reticle_size), color, 1)

def draw_scan_laser(frame: np.ndarray, x: int, y: int, w: int, h: int, frame_tick: int, color=HUD_COLOR) -> None:
    scan_margin = max(6, h // 10)
    scan_top = y + scan_margin
    scan_bottom = y + h - scan_margin
    if scan_bottom <= scan_top:
        scan_top = y
        scan_bottom = y + h
    travel = max(1, scan_bottom - scan_top)
    phase = 0.5 + 0.5 * math.sin(frame_tick * 0.08)
    scan_y = scan_top + int(travel * phase)
    cv2.line(frame, (x + 4, scan_y), (x + w - 4, scan_y), color, 1)

def draw_telemetry(frame: np.ndarray, x: int, y: int, w: int, h: int, identity_text: str, color=HUD_COLOR) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.42
    thickness = 1
    cv2.putText(frame, identity_text, (x, max(16, y - 24)), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(frame, f"X_COORD: {x}", (x, y + h + 16), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(frame, f"Y_COORD: {y}", (x, y + h + 31), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(frame, "SYS_LOCK: ACTIVE", (x, y + h + 46), font, scale, color, thickness, cv2.LINE_AA)

def draw_hud(frame: np.ndarray, box: Tuple[int, int, int, int], frame_tick: int, identity_text: str) -> None:
    x, y, w, h = box
    draw_corner_brackets(frame, x, y, w, h)
    draw_scan_laser(frame, x, y, w, h, frame_tick)
    draw_reticle(frame, x, y, w, h)
    draw_telemetry(frame, x, y, w, h, identity_text)

def select_primary_face(frame_locations: List[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    if not frame_locations:
        return None
    return max(frame_locations, key=face_location_area)

def build_frame_stream() -> bytes:
    global current_live_frame
    with camera_lock:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        box_history: List[Tuple[int, int, int, int]] = []
        last_box: Optional[Tuple[int, int, int, int]] = None
        last_identity_text = "[ TARGET_UNKNOWN: UNKNOWN ]"
        missed_frames = 0
        frame_tick = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Populates global memory so registration pulls instantly from here
                current_live_frame = frame.copy()

                small_frame = cv2.resize(frame, (0, 0), fx=STREAM_SCALE, fy=STREAM_SCALE)
                rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_small, model="hog")
                face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

                candidate_box: Optional[Tuple[int, int, int, int]] = None
                candidate_identity_text = "[ TARGET_UNKNOWN: UNKNOWN ]"

                if face_locations and face_encodings:
                    primary_location = select_primary_face(face_locations)
                    if primary_location is not None:
                        primary_index = face_locations.index(primary_location)
                        face_encoding = face_encodings[primary_index]
                        employee_id, is_match, confidence = match_employee(face_encoding)

                        if is_match and employee_id is not None:
                            candidate_identity_text = f"[ AUTHENTICATED: {build_employee_display_name(employee_id)} ]"
                            queue_attendance_log(employee_id)
                        else:
                            candidate_identity_text = "[ TARGET_UNKNOWN: UNKNOWN ]"

                        candidate_box = clamp_box(
                            location_to_box(primary_location, scale_factor=1.0 / STREAM_SCALE),
                            frame.shape[1],
                            frame.shape[0],
                        )

                if candidate_box is not None:
                    box_history.append(candidate_box)
                    if len(box_history) > 8:
                        box_history.pop(0)
                    last_box = average_box_history(box_history)
                    last_identity_text = candidate_identity_text
                    missed_frames = 0
                else:
                    missed_frames += 1
                    if missed_frames > 15:
                        box_history.clear()
                        last_box = None
                        last_identity_text = "[ TARGET_UNKNOWN: UNKNOWN ]"

                if last_box is not None:
                    x, y, w, h = clamp_box(last_box, frame.shape[1], frame.shape[0])
                    draw_hud(frame, (x, y, w, h), frame_tick, last_identity_text)

                success, jpeg_buffer = cv2.imencode(".jpg", frame)
                if not success:
                    continue

                frame_bytes = jpeg_buffer.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
                frame_tick += 1
        finally:
            cap.release()

@app.get("/api/stream")
def stream_webcam() -> StreamingResponse:
    return StreamingResponse(
        build_frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@app.post("/api/register")
def register_employee(payload: RegisterRequest, background_tasks: BackgroundTasks):
    global current_live_frame
    cleaned_name = clean_text(payload.name)
    cleaned_title = clean_display_text(payload.title)

    if not cleaned_name or not cleaned_title:
        raise HTTPException(status_code=400, detail="Name and Title fields cannot be blank.")

    # Safety catch to ensure user is running the web stream interface
    if current_live_frame is None:
        raise HTTPException(status_code=503, detail="Active live stream feed required to parse biometric data.")

    try:
        inserted = supabase.table(DATABASE_TABLE).insert(
            {"name": cleaned_name, "title": cleaned_title}
        ).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database record generation failed: {exc}")

    inserted_rows = inserted.data or []
    if not inserted_rows:
        raise HTTPException(status_code=500, detail="Employee record not returned.")

    employee_id = int(inserted_rows[0]["id"])
    bucket = supabase.storage.from_(SUPABASE_BUCKET)
    captured_faces: List[bytes] = []

    print(f"Starting biometric extraction loop for employee ID: {employee_id}")

    # Seamless extraction from stream matrix instead of locking physical hardware resources
    for check_cycle in range(40):
        if len(captured_faces) >= 15: 
            break

        frame = current_live_frame.copy() if current_live_frame is not None else None
        if frame is None:
            time.sleep(0.05)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

        face_box = choose_largest_face(faces)
        if face_box is not None:
            x, y, w, h = clamp_box(face_box, frame.shape[1], frame.shape[0])
            face_crop = frame[y : y + h, x : x + w]
            if face_crop.size > 0:
                face_gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                face_gray = cv2.resize(face_gray, FACE_IMAGE_SIZE)
                success, encoded = cv2.imencode(".jpg", face_gray)
                if success:
                    captured_faces.append(encoded.tobytes())
        
        # Short timeout to yield to context worker thread and allow new camera frames to enter memory buffer
        time.sleep(0.06)

    print(f"Total biometric frames extracted safely: {len(captured_faces)}")

    if not captured_faces:
        raise HTTPException(status_code=400, detail="Could not capture signature frames. Ensure face remains visible within view.")

    # Upload clean arrays directly to storage directory bucket matching user name reference
    for index, face_bytes in enumerate(captured_faces, start=1):
        object_path = f"{cleaned_name}/face_{index}.jpg"
        try:
            bucket.upload(object_path, face_bytes, file_options={"content-type": "image/jpeg", "upsert": "true"})
        except Exception as upload_err:
            print(f"Failed to push avatar object index {index}: {upload_err}")
            continue

    print("Biometric profiles loaded into cloud database bucket successfully.")
    background_tasks.add_task(sync_employee_models)
    return {"message": "Success", "employee_id": employee_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)