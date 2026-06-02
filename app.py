import os
import sys
import math
import glob

import cv2
import numpy as np


FACE_SIZE = (200, 200)
MATCH_CONFIDENCE_THRESHOLD = 115.0
HUD_COLOR = (255, 191, 0)


def require_face_module():
    if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
        raise RuntimeError(
            "OpenCV face recognizer is unavailable. Install opencv-contrib-python so cv2.face is present."
        )


def detect_faces(cascade, gray_frame):
    faces = cascade.detectMultiScale(
        gray_frame,
        scaleFactor=1.05,
        minNeighbors=3,
        minSize=(30, 30),
    )
    return [tuple(map(int, face)) for face in faces]


def group_face_rectangles(rectangles):
    rect_list = [list(map(int, rect)) for rect in rectangles]
    if not rect_list:
        return []

    grouped_rectangles, _ = cv2.groupRectangles(rect_list + rect_list, groupThreshold=1, eps=0.2)
    if len(grouped_rectangles) == 0:
        return [tuple(rect) for rect in rect_list]

    return [tuple(map(int, rect)) for rect in grouped_rectangles]


def open_camera():
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(0, backend)
        if cap.isOpened():
            return cap
        cap.release()

    return cv2.VideoCapture(0)


def load_cascades():
    frontal_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    profile_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_profileface.xml"
    )

    if frontal_cascade.empty():
        raise RuntimeError("Failed to load Haar cascade frontal face classifier.")
    if profile_cascade.empty():
        raise RuntimeError("Failed to load Haar cascade profile face classifier.")

    return frontal_cascade, profile_cascade


def preprocess_face(gray_face):
    resized_face = cv2.resize(gray_face, FACE_SIZE)
    return cv2.equalizeHist(resized_face)


def expand_box(x, y, w, h, image_width, image_height, padding_ratio=0.18):
    pad_w = int(w * padding_ratio)
    pad_h = int(h * padding_ratio)

    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(image_width, x + w + pad_w)
    y2 = min(image_height, y + h + pad_h)

    expanded_w = max(1, x2 - x1)
    expanded_h = max(1, y2 - y1)
    return x1, y1, expanded_w, expanded_h


def find_largest_face(gray_image, frontal_cascade, profile_cascade):
    image_height, image_width = gray_image.shape
    detections = []

    detections.extend(detect_faces(frontal_cascade, gray_image))
    detections.extend(detect_faces(profile_cascade, gray_image))

    flipped_gray = cv2.flip(gray_image, 1)
    for (x, y, w, h) in detect_faces(profile_cascade, flipped_gray):
        x_original = image_width - x - w
        detections.append((x_original, y, w, h))

    grouped_faces = group_face_rectangles(detections)
    if not grouped_faces:
        return None

    x, y, w, h = max(grouped_faces, key=lambda rect: rect[2] * rect[3])
    x, y, w, h = expand_box(x, y, w, h, image_width, image_height, padding_ratio=0.12)
    return x, y, w, h


def augment_training_face(gray_face):
    augmented_faces = [gray_face]
    augmented_faces.append(cv2.flip(gray_face, 1))
    augmented_faces.append(cv2.convertScaleAbs(gray_face, alpha=1.08, beta=8))
    augmented_faces.append(cv2.convertScaleAbs(gray_face, alpha=0.92, beta=-6))
    return [preprocess_face(face) for face in augmented_faces]


def load_person_training_data(person_name, person_label, frontal_cascade, profile_cascade):
    person_files = sorted(
        file_path
        for file_path in glob.glob(os.path.join(os.getcwd(), f"{person_name}*"))
        if os.path.isfile(file_path)
    )

    if not person_files:
        print(
            f"Error: no training photos were found for {person_name.title()}. "
            f"Add files named like '{person_name} face 1.jpg' in the current folder."
        )
        sys.exit(1)

    person_training_data = []
    person_labels = []

    for file_path in person_files:
        reference_image = cv2.imread(file_path)
        if reference_image is None:
            print(f"Warning: could not read '{os.path.basename(file_path)}'; skipping.")
            continue

        reference_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
        face_box = find_largest_face(reference_gray, frontal_cascade, profile_cascade)
        if face_box is None:
            print(f"Warning: no face detected in '{os.path.basename(file_path)}'; skipping.")
            continue

        x, y, w, h = face_box
        face_crop = reference_gray[y : y + h, x : x + w]
        if face_crop.size == 0:
            print(f"Warning: empty crop in '{os.path.basename(file_path)}'; skipping.")
            continue

        for prepared_face in augment_training_face(face_crop):
            person_training_data.append(prepared_face)
            person_labels.append(person_label)

    if not person_training_data:
        print(f"Error: no valid face samples were extracted for {person_name.title()}.")
        sys.exit(1)

    return person_training_data, person_labels


def load_training_data(frontal_cascade, profile_cascade):
    training_data = []
    labels = []

    hiruna_data, hiruna_labels = load_person_training_data("hiruna", 1, frontal_cascade, profile_cascade)
    manoj_data, manoj_labels = load_person_training_data("manoj", 2, frontal_cascade, profile_cascade)

    training_data.extend(hiruna_data)
    training_data.extend(manoj_data)
    labels.extend(hiruna_labels)
    labels.extend(manoj_labels)

    if not training_data:
        print("Error: no valid face samples were extracted from the available training photos.")
        sys.exit(1)

    return training_data, labels


def train_recognizer(training_data, labels):
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(training_data, np.array(labels, dtype=np.int32))
    return recognizer


def scan_frame(gray, frontal_cascade, profile_cascade):
    frame_height, frame_width = gray.shape
    detections = []

    detections.extend(detect_faces(frontal_cascade, gray))
    detections.extend(detect_faces(profile_cascade, gray))

    gray_flipped = cv2.flip(gray, 1)
    for (x, y, w, h) in detect_faces(profile_cascade, gray_flipped):
        x_original = frame_width - x - w
        detections.append((x_original, y, w, h))

    grouped_faces = group_face_rectangles(detections)

    clipped_faces = []
    for x, y, w, h in grouped_faces:
        x, y, w, h = expand_box(x, y, w, h, frame_width, frame_height, padding_ratio=0.08)
        if w > 0 and h > 0:
            clipped_faces.append((x, y, w, h))

    return clipped_faces


def classify_face(recognizer, gray_face):
    prepared_face = preprocess_face(gray_face)
    label, confidence = recognizer.predict(prepared_face)
    is_match = label == 1 and confidence < MATCH_CONFIDENCE_THRESHOLD
    return is_match, label, confidence


def average_box_history(box_history):
    count = len(box_history)
    if count == 0:
        return None

    x_total = sum(box[0] for box in box_history)
    y_total = sum(box[1] for box in box_history)
    w_total = sum(box[2] for box in box_history)
    h_total = sum(box[3] for box in box_history)

    return (
        int(round(x_total / count)),
        int(round(y_total / count)),
        int(round(w_total / count)),
        int(round(h_total / count)),
    )


def select_target_box(face_boxes):
    if not face_boxes:
        return None

    return max(face_boxes, key=lambda rect: rect[2] * rect[3])


def draw_corner_brackets(frame, x, y, w, h, color=HUD_COLOR, thickness=2):
    corner_length = max(12, min(w, h) // 5)

    cv2.line(frame, (x, y), (x + corner_length, y), color, thickness)
    cv2.line(frame, (x, y), (x, y + corner_length), color, thickness)

    cv2.line(frame, (x + w, y), (x + w - corner_length, y), color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + corner_length), color, thickness)

    cv2.line(frame, (x, y + h), (x + corner_length, y + h), color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - corner_length), color, thickness)

    cv2.line(frame, (x + w, y + h), (x + w - corner_length, y + h), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - corner_length), color, thickness)


def draw_reticle(frame, x, y, w, h, color=HUD_COLOR):
    center_x = x + w // 2
    center_y = y + h // 2
    reticle_size = max(4, min(w, h) // 12)

    cv2.circle(frame, (center_x, center_y), 2, color, -1)
    cv2.line(frame, (center_x - reticle_size, center_y), (center_x + reticle_size, center_y), color, 1)
    cv2.line(frame, (center_x, center_y - reticle_size), (center_x, center_y + reticle_size), color, 1)


def draw_scan_laser(frame, x, y, w, h, frame_tick, color=HUD_COLOR):
    scan_margin = max(6, h // 10)
    top = y + scan_margin
    bottom = y + h - scan_margin
    if bottom <= top:
        top = y
        bottom = y + h

    travel = max(1, bottom - top)
    phase = 0.5 + 0.5 * math.sin(frame_tick * 0.08)
    scan_y = top + int(travel * phase)

    cv2.line(frame, (x + 4, scan_y), (x + w - 4, scan_y), color, 1)


def draw_telemetry(frame, x, y, w, h, label, confidence, color=HUD_COLOR):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.42
    thickness = 1

    if label == 1 and confidence < MATCH_CONFIDENCE_THRESHOLD:
        status_text = "[ AUTHENTICATED: HR - HIRUNA ]"
    elif label == 2 and confidence < MATCH_CONFIDENCE_THRESHOLD:
        status_text = "[ AUTHENTICATED: EMPLOYEE - MANOJ ]"
    else:
        status_text = "[ TARGET_UNKNOWN: SCANNING... ]"

    coords_x = f"X_COORD: {x}"
    coords_y = f"Y_COORD: {y}"
    lock_text = "SYS_LOCK: ACTIVE"

    cv2.putText(frame, status_text, (x, max(16, y - 24)), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(frame, coords_x, (x, y + h + 16), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(frame, coords_y, (x, y + h + 31), font, scale, color, thickness, cv2.LINE_AA)
    cv2.putText(frame, lock_text, (x, y + h + 46), font, scale, color, thickness, cv2.LINE_AA)


def draw_hud(frame, box, frame_tick, label, confidence):
    x, y, w, h = box
    draw_corner_brackets(frame, x, y, w, h)
    draw_scan_laser(frame, x, y, w, h, frame_tick)
    draw_reticle(frame, x, y, w, h)
    draw_telemetry(frame, x, y, w, h, label, confidence)


def main():
    require_face_module()
    frontal_cascade, profile_cascade = load_cascades()

    training_data, labels = load_training_data(frontal_cascade, profile_cascade)
    recognizer = train_recognizer(training_data, labels)

    cap = open_camera()
    if not cap.isOpened():
        raise RuntimeError("Could not open the webcam.")

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    window_name = "Hiruna Face Tracking"

    try:
        box_history = []
        last_smoothed_box = None
        missed_frames = 0
        frame_tick = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_boxes = scan_frame(gray, frontal_cascade, profile_cascade)
            target_box = select_target_box(face_boxes)

            if target_box is not None:
                box_history.append(target_box)
                if len(box_history) > 8:
                    box_history.pop(0)
                last_smoothed_box = average_box_history(box_history)
                missed_frames = 0
            else:
                missed_frames += 1
                if missed_frames > 15:
                    box_history.clear()
                    last_smoothed_box = None

            display_box = last_smoothed_box

            if display_box is not None:
                x, y, w, h = display_box
                face_crop = gray[y : y + h, x : x + w]
                if face_crop.size == 0:
                    display_box = None
                else:
                    try:
                        is_match, label, confidence = classify_face(recognizer, face_crop)
                    except cv2.error:
                        is_match = False
                        label = -1
                        confidence = 999.0

                    print(f"Detected Label: {label}, Confidence Score: {confidence}")

                    draw_hud(frame, display_box, frame_tick, label if is_match else -1, confidence)

            cv2.imshow(window_name, frame)
            frame_tick += 1

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
