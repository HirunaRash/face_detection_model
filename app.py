import cv2


def main():
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_profileface.xml"
    )

    if face_cascade.empty():
        raise RuntimeError("Failed to load Haar cascade profile face classifier.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open the webcam.")

    window_name = "Real-Time Side-Profile Face Detection"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame_height, frame_width = gray.shape
            
            # Detect left-facing profiles in the normal frame
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )

            # Draw left-facing profiles
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Flip the grayscale frame horizontally to detect right-facing profiles
            gray_flipped = cv2.flip(gray, 1)
            faces_flipped = face_cascade.detectMultiScale(
                gray_flipped,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )

            # Convert flipped coordinates back to original frame space and draw
            for (x, y, w, h) in faces_flipped:
                # Transform x coordinate from flipped frame to original frame
                x_original = frame_width - x - w
                cv2.rectangle(frame, (x_original, y), (x_original + w, y + h), (0, 255, 0), 2)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
