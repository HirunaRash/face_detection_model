import cv2


def detect_faces(cascade, gray_frame):
    faces = cascade.detectMultiScale(
        gray_frame,
        scaleFactor=1.05,
        minNeighbors=3,
        minSize=(30, 30),
    )
    return [tuple(face) for face in faces]


def box_iou(box_a, box_b):
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b

    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = aw * ah
    area_b = bw * bh
    union_area = area_a + area_b - inter_area

    if union_area == 0:
        return 0.0

    return inter_area / union_area


def overlap_ratio(box_a, box_b):
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b

    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    smaller_area = min(aw * ah, bw * bh)
    if smaller_area == 0:
        return 0.0

    return inter_area / smaller_area


def merge_overlapping_boxes(boxes, iou_threshold=0.2, overlap_threshold=0.65):
    if not boxes:
        return []

    ordered_boxes = sorted(boxes, key=lambda box: box[2] * box[3], reverse=True)
    kept_boxes = []

    for candidate in ordered_boxes:
        if all(
            box_iou(candidate, kept) < iou_threshold
            and overlap_ratio(candidate, kept) < overlap_threshold
            for kept in kept_boxes
        ):
            kept_boxes.append(candidate)

    return kept_boxes


def open_camera():
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(0, backend)
        if cap.isOpened():
            return cap
        cap.release()

    return cv2.VideoCapture(0)


def main():
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

    cap = open_camera()
    if not cap.isOpened():
        raise RuntimeError("Could not open the webcam.")

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    window_name = "Real-Time Face Detection"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame_height, frame_width = gray.shape
            detections = []

            detections.extend(detect_faces(frontal_cascade, gray))
            detections.extend(detect_faces(profile_cascade, gray))

            gray_flipped = cv2.flip(gray, 1)
            for (x, y, w, h) in detect_faces(profile_cascade, gray_flipped):
                x_original = frame_width - x - w
                detections.append((x_original, y, w, h))

            for (x, y, w, h) in merge_overlapping_boxes(detections):
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
