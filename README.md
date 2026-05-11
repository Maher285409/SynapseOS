# 🖐️ SynapseOS Lite — AI Hand Gesture Controller

Control your entire computer with just your hand using real-time computer vision. No mouse, no keyboard — just gestures.

Built with Python, OpenCV, and MediaPipe.

---

## ✨ Demo

> Point one finger at the camera and your cursor follows. Pinch to click. Peace sign to scroll. Three fingers to control volume. Make a fist to lock everything.

---

## 🎯 Gesture Map

| Gesture  | Fingers             | Action                       |
| -------- | ------------------- | ---------------------------- |
| ✊ Fist  | 0                   | Lock / Unlock the system     |
| ☝️ Point | 1                   | Move mouse cursor            |
| 🤏 Pinch | Thumb + Index close | Left click                   |
| ✌️ Peace | 2                   | Scroll — move hand up/down   |
| 🤚 Three | 3                   | Volume — raise hand = louder |

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/synapse-os-lite.git
cd synapse-os-lite
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python synapse_os.py
```

Press **Q** to quit.

---

## 🛠️ Requirements

- Python 3.9+
- Webcam
- Windows (volume control uses `pycaw` which is Windows-only — all other features work cross-platform)

---

## ⚙️ Configuration

Open `synapse_os.py` and tweak the values at the top:

```python
MOUSE_SMOOTH  = 6    # higher = smoother but slower cursor
SCROLL_SPEED  = 15   # increase if scrolling feels slow
PINCH_DIST    = 36   # px distance between thumb+index that counts as a click
VOL_SMOOTH    = 4    # lower = snappier volume response
```

---

## 📦 Tech Stack

| Library                                       | Purpose                                 |
| --------------------------------------------- | --------------------------------------- |
| [MediaPipe](https://mediapipe.dev)            | Hand landmark detection (21 points)     |
| [OpenCV](https://opencv.org)                  | Camera capture + drawing the HUD        |
| [PyAutoGUI](https://pyautogui.readthedocs.io) | Moving the mouse + clicking + scrolling |
| [pycaw](https://github.com/AndreMiras/pycaw)  | Windows system volume control           |
| NumPy                                         | Coordinate mapping + smoothing math     |

---

## 💡 How It Works

MediaPipe detects 21 hand landmarks in real time. The script reads which fingers are raised, maps the index fingertip position to screen coordinates, and sends the right system calls depending on the gesture. A stability gate (gesture must hold for 0.2s) prevents accidental triggers.

---

## 🔮 Ideas for Future Features

- Right-click gesture
- Multi-monitor support
- Brightness control
- Custom gesture mapping via config file
- Two-hand support

---

## 🙋 Author

Made by **[Your Name]** — feel free to fork, star, and improve it!
