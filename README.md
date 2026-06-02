# Real-Time Face Recognition (Webcam)

This project provides a Python application for real-time face recognition using a webcam with:

- `opencv-python` (`cv2`) for webcam capture and display
- `face_recognition` for face detection and encoding comparison

## Prerequisites

`face_recognition` depends on `dlib`, which may require system build tools.

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3 python3-pip cmake build-essential libopenblas-dev liblapack-dev
```

### macOS (Homebrew)

```bash
brew install cmake
```

### Windows

- Install **Visual Studio Build Tools** (C++ build tools)
- Install **CMake** and add it to PATH

## Installation

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Reference Image Setup

Place a clear image named exactly:

```text
manoj.jpg
```

in the repository root:

```text
<repository-root>/manoj.jpg
```

The application loads this image at startup and extracts Manoj's face encoding.
For best results, use a front-facing image with good lighting and one clearly visible face.

## Run the Application

```bash
python app.py
```

Press `q` in the webcam window to quit.

## Behavior

- If a detected face matches Manoj's encoding:
  - Green bounding box
  - Label: `Hi Manoj`
- If no match:
  - Red bounding box
  - Label: `Unknown Person`

## Error Handling

The app exits with a clear message if:

- `manoj.jpg` is missing
- no face can be encoded from `manoj.jpg`
- the webcam cannot be opened