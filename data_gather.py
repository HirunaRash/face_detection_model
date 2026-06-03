import os

import cv2
import numpy as np


TARGET_COUNT = 300
FACE_SIZE = (200, 200)


def sanitize_name(raw_name):
    cleaned = raw_name.strip()
    cleaned = cleaned.replace("/", "_").replace("\\", "_")
    cleaned = cleaned.replace(":", "_").replace("*", "_")
    cleaned = cleaned.replace("?", "_").replace('"', "_")
    cleaned = cleaned.replace("<", "_").replace(">", "_")
    cleaned = cleaned.replace("|", "_")
    cleaned = "_".join(part for part in cleaned.split())
    return cleaned.strip("._ ")


def choose_largest_face(faces):
    if len(faces) == 0:
        return None
    return max(faces, key=lambda face: face[2] * face[3])


def clamp_face_box(x, y, w, h, frame_width, frame_height):
    x = max(0, x)
    y = max(0, y)
    w = min(w, frame_width - x)
    h = min(h, frame_height - y)
    return x, y, w, h


def main():
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    if face_cascade.empty():
        raise RuntimeError("Failed to load Haar cascade face detector.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open the webcam.")

    captured_faces = []
    window_name = "Face Data Capture"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Warning: could not read from webcam.")
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
            )

            face_box = choose_largest_face(faces)
            if face_box is not None and len(captured_faces) < TARGET_COUNT:
                x, y, w, h = face_box
                x, y, w, h = clamp_face_box(x, y, w, h, frame.shape[1], frame.shape[0])

                if w > 0 and h > 0:
                    face_crop = frame[y : y + h, x : x + w]
                    face_gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                    resized_face = cv2.resize(face_gray, FACE_SIZE)
                    captured_faces.append(resized_face.copy())
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            current_count = len(captured_faces)
            progress_text = f"Scanning: {current_count} / {TARGET_COUNT}"
            instruction_text = "Slowly rotate and tilt your head"

            cv2.putText(
                frame,
                progress_text,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                instruction_text,
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, frame)

            if current_count >= TARGET_COUNT:
                print("Face capture complete: 300 face crops saved to memory.")
                break

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("Capture stopped by user.")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not captured_faces:
        print("No face crops were captured. Nothing to save.")
        return

    raw_name = input("Enter name for this user: ")
    dataset_name = sanitize_name(raw_name)

    if not dataset_name:
        print("Error: dataset name cannot be empty.")
        return

    dataset_dir = os.path.join("dataset", dataset_name)
    os.makedirs(dataset_dir, exist_ok=True)

    for index, face_crop in enumerate(captured_faces, start=1):
        file_path = os.path.join(dataset_dir, f"user_{index}.jpg")
        cv2.imwrite(file_path, face_crop)

    print(f"Success: saved {len(captured_faces)} face crops to {dataset_dir}.")


if __name__ == "__main__":
    main()
