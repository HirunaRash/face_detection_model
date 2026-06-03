import cv2
import numpy as np
import os

def load_and_train_dataset():
    dataset_dir = "dataset"
    if not os.path.exists(dataset_dir) or len(os.listdir(dataset_dir)) == 0:
        print("No registered employees found. Please run data_gather.py first!")
        return None, {}

    # Initialize the OpenCV Local Binary Patterns Histograms recognizer
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    
    faces_data = []
    labels_data = []
    id_to_name = {}
    current_id = 1

    print("Loading biometric database maps...")
    for folder_name in os.listdir(dataset_dir):
        folder_path = os.path.join(dataset_dir, folder_name)
        if os.path.isdir(folder_path):
            id_to_name[current_id] = folder_name
            
            for file_name in os.listdir(folder_path):
                if file_name.endswith(('.jpg', '.jpeg', '.png')):
                    img_path = os.path.join(folder_path, file_name)
                    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    
                    if img is not None:
                        faces_data.append(img)
                        labels_data.append(current_id)
            current_id += 1

    if len(faces_data) == 0:
        return None, {}

    print("Training patterns... System starting up.")
    recognizer.train(faces_data, np.array(labels_data))
    return recognizer, id_to_name

def main():
    recognizer, id_to_name = load_and_train_dataset()
    if recognizer is None:
        return

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0)
    
    # Tracking Filter Cache to stop the "giggling" error
    coord_history = []
    frame_count = 0
    scan_y_dir = 1
    scan_y_pos = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
        
        target_box = None
        
        if len(faces) > 0:
            # Sort to grab the largest face in front of camera
            faces = sorted(faces, key=lambda b: b[2]*b[3], reverse=True)
            coord_history.append(faces[0])
            if len(coord_history) > 8:
                coord_history.pop(0)
        elif len(coord_history) > 0:
            # Brief hold if face drops for a frame
            if frame_count % 5 == 0:
                coord_history.pop(0)

        if len(coord_history) > 0:
            # Apply linear smoothing filter across history frames to prevent giggling
            target_box = np.mean(coord_history, axis=0).astype(int)

        if target_box is not None:
            x, y, w, h = target_box
            live_crop = gray[y:y+h, x:x+w]
            
            name_text = "UNKNOWN"
            if live_crop.size > 0:
                live_crop_resized = cv2.resize(live_crop, (200, 200))
                label_id, confidence = recognizer.predict(live_crop_resized)
                
                # Confidence score check for dynamic role tagging
                if confidence < 95:
                    raw_name = id_to_name.get(label_id, "User")
                    # Dynamically add custom titles depending on who is detected
                    if raw_name.lower() == "hiruna":
                        name_text = "HR - Hiruna"
                    elif raw_name.lower() == "manoj":
                        name_text = "Employee - Manoj"
                    else:
                        name_text = f"Employee - {raw_name.capitalize()}"

            # UI HUD Color Setup - Cyber Blue (BGR: 255, 191, 0)
            hud_color = (255, 191, 0)
            
            # 1. Tech Corner Brackets
            d = 20 # Line length
            t = 3  # Thickness
            cv2.line(frame, (x, y), (x + d, y), hud_color, t)
            cv2.line(frame, (x, y), (x, y + d), hud_color, t)
            cv2.line(frame, (x + w, y), (x + w - d, y), hud_color, t)
            cv2.line(frame, (x + w, y), (x + w, y + d), hud_color, t)
            cv2.line(frame, (x, y + h), (x + d, y + h), hud_color, t)
            cv2.line(frame, (x, y + h), (x, y + h - d), hud_color, t)
            cv2.line(frame, (x + w, y + h), (x + w - d, y + h), hud_color, t)
            cv2.line(frame, (x + w, y + h), (x + w, y + h - d), hud_color, t)
            
            # 2. Center Reticle Target Crosshair
            cx, cy = x + w // 2, y + h // 2
            cv2.circle(frame, (cx, cy), 3, hud_color, -1)
            
            # 3. Animated Scanning Laser Line
            scan_y_pos += 4 * scan_y_dir
            if scan_y_pos >= h or scan_y_pos <= 0:
                scan_y_dir *= -1
            current_laser_y = y + scan_y_pos
            cv2.line(frame, (x + 5, current_laser_y), (x + w - 5, current_laser_y), hud_color, 1)
            
            # 4. Telemetry Layout Strings
            if "UNKNOWN" in name_text:
                status_str = f"[ TARGET_UNKNOWN: {name_text} ]"
            else:
                status_str = f"[ AUTHENTICATED: Hi {name_text} ]"
                
            cv2.putText(frame, status_str, (x, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, hud_color, 2)
            cv2.putText(frame, f"X_COORD: {cx}  Y_COORD: {cy}", (x, y + h + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, hud_color, 1)
            cv2.putText(frame, "SYS_LOCK: ACTIVE", (x, y + h + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.4, hud_color, 1)

        cv2.imshow("Cybernetic Biometric HUD Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()