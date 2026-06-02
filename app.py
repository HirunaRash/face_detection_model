"""Real-time face recognition with webcam feed."""

from pathlib import Path
import sys

import cv2
import face_recognition


def load_known_face_encoding(image_path: Path):
    """Load and encode Manoj's face from the reference image."""
    if not image_path.exists():
        raise FileNotFoundError(f"Reference image not found: {image_path}")

    known_image = face_recognition.load_image_file(str(image_path))
    known_encodings = face_recognition.face_encodings(known_image)
    if not known_encodings:
        raise ValueError(f"No face found in reference image: {image_path}")

    return known_encodings[0]


def main():
    """Run webcam loop and compare live faces with Manoj's encoding."""
    project_root = Path(__file__).resolve().parent
    reference_image_path = project_root / "manoj.jpg"

    try:
        manoj_encoding = load_known_face_encoding(reference_image_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        print("Error: Could not open webcam.")
        return 1

    try:
        while True:
            # Read one frame from the webcam.
            ret, frame = video_capture.read()
            if not ret:
                print("Error: Failed to read frame from webcam.")
                break

            # Convert BGR (OpenCV) frame to RGB for face_recognition.
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces and compute their encodings in current frame.
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                # Compare each live encoding against Manoj's known encoding.
                matches = face_recognition.compare_faces([manoj_encoding], face_encoding)
                distance = face_recognition.face_distance([manoj_encoding], face_encoding)[0]
                is_match = matches[0] and distance < 0.5

                if is_match:
                    color = (0, 255, 0)  # Green
                    label = "Hi Manoj"
                else:
                    color = (0, 0, 255)  # Red
                    label = "Unknown Person"

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(
                    frame,
                    label,
                    (left, max(top - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2,
                )

            cv2.imshow("Face Recognition", frame)

            # Press "q" to quit the application.
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        video_capture.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
