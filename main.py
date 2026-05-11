"""
SynapseOS Lite — Hand Gesture Controller
══════════════════════════════════════════════════════
  GESTURE MAP  (printed on screen while running)

  ✊  FIST      →  Lock / Unlock the system
  ☝️   1 finger  →  Move mouse cursor
              bring thumb close to index = LEFT CLICK
  ✌️  2 fingers  →  Scroll  — move hand UP = scroll up
                              move hand DOWN = scroll down
  🤚  3 fingers  →  Volume  — raise hand HIGH = louder
                              lower hand DOWN = quieter

  Q key → Quit
══════════════════════════════════════════════════════
INSTALL:
  pip install opencv-python mediapipe pyautogui numpy pycaw comtypes
"""

import math
import time
from ctypes import POINTER, cast

import cv2
import mediapipe as mp
import numpy as np
import pyautogui
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# ──────────────────────────────────────────────────────
#  TWEAK THESE if things feel too fast / slow / jittery
# ──────────────────────────────────────────────────────
MOUSE_SMOOTH = 6  # higher = glider mouse, lower = snappy
MARGIN = 20  # camera-edge dead zone (px) for mouse mapping
PINCH_DIST = 36  # px threshold for click pinch
CLICK_CD = 0.5  # min seconds between clicks
LOCK_CD = 1.2  # min seconds between lock toggles
HOLD_TIME = 0.20  # seconds a gesture must be stable before activating
SCROLL_SPEED = 15  # scroll ticks per frame (raise if still slow on your machine)
VOL_SMOOTH = 4  # lower = snappier volume response
# ──────────────────────────────────────────────────────

pyautogui.FAILSAFE = False

# ── CAMERA ────────────────────────────────────────────
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)
screenW, screenH = pyautogui.size()

# ── STATE ─────────────────────────────────────────────
prevMouseX, prevMouseY = 0, 0
prevHandY = None  # for scroll delta
smoothVolPct = 50.0  # smoothed volume % (avoids jumpy bar)
lastClickTime = 0
lastLockTime = 0
gestureStart = 0
lastGesture = -1
systemActive = True
prevTime = time.time()

# ── MEDIAPIPE ─────────────────────────────────────────
mpHands = mp.solutions.hands
hands = mpHands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.85,
    min_tracking_confidence=0.80,
)
mpDraw = mp.solutions.drawing_utils
dot_style = mpDraw.DrawingSpec(color=(0, 255, 120), thickness=2, circle_radius=3)
conn_style = mpDraw.DrawingSpec(color=(180, 180, 180), thickness=1)

# ── VOLUME  (Windows only — silently disabled elsewhere) ──
volumeEnabled = False
volume = None
minVol = 0.0
maxVol = 0.0
volErrorMsg = ""  # shown on screen if init fails
try:
    devices = AudioUtilities.GetSpeakers()
    # newer pycaw wraps the device — unwrap if needed
    dev = getattr(devices, "_dev", devices)
    interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    vr = volume.GetVolumeRange()
    minVol, maxVol = vr[0], vr[1]
    volumeEnabled = True
    print("[Volume] Initialized OK  —  range:", minVol, "to", maxVol, "dB")
except Exception as e:
    volErrorMsg = str(e)[:55]  # truncate so it fits on screen
    print(f"[Volume] Not available: {e}")


# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════


def count_fingers(lm):
    """Count raised fingers: index, middle, ring, pinky (thumb excluded)."""
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    return sum(1 for t, p in zip(tips, pips) if lm[t][2] < lm[p][2])


def panel(img, x, y, pw, ph, alpha=0.65):
    ov = img.copy()
    cv2.rectangle(ov, (x, y), (x + pw, y + ph), (8, 8, 8), -1)
    cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)


def lbl(img, text, pos, scale=0.52, color=(210, 210, 210), thick=1):
    cv2.putText(
        img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA
    )


def vol_color(pct):
    """BGR: green(0%) → yellow(50%) → red(100%)."""
    r = int(np.interp(pct, [0, 50, 100], [0, 255, 255]))
    g = int(np.interp(pct, [0, 50, 100], [210, 210, 0]))
    return (0, g, r)


# ══════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════
while True:
    ok, img = cap.read()
    if not ok:
        continue

    img = cv2.flip(img, 1)
    h, w = img.shape[:2]
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    res = hands.process(imgRGB)

    lmList = []
    totalFingers = 0
    mode = "---"
    now = time.time()

    if res.multi_hand_landmarks:
        handLms = res.multi_hand_landmarks[0]

        for _id, lm in enumerate(handLms.landmark):
            lmList.append([_id, int(lm.x * w), int(lm.y * h)])

        mpDraw.draw_landmarks(
            img, handLms, mpHands.HAND_CONNECTIONS, dot_style, conn_style
        )

        if len(lmList) == 21:

            thumbTip = lmList[4]
            indexTip = lmList[8]
            midTip = lmList[12]
            wrist = lmList[0]

            x1, y1 = thumbTip[1], thumbTip[2]
            x2, y2 = indexTip[1], indexTip[2]
            pinchLen = math.hypot(x2 - x1, y2 - y1)

            totalFingers = count_fingers(lmList)

            # ── GESTURE STABILITY GATE ──────────────────
            if totalFingers != lastGesture:
                gestureStart = now
                lastGesture = totalFingers
                prevHandY = None  # reset scroll anchor on gesture change
            gestureReady = (now - gestureStart) >= HOLD_TIME

            # ── FIST → LOCK / UNLOCK ────────────────────
            if totalFingers == 0 and gestureReady:
                if now - lastLockTime > LOCK_CD:
                    systemActive = not systemActive
                    lastLockTime = now

            if systemActive:

                # ════════════════════════════════════════
                #  1 FINGER → MOUSE  +  PINCH = CLICK
                # ════════════════════════════════════════
                if totalFingers == 1 and gestureReady:
                    mode = "MOUSE"

                    rawX = np.interp(x2, [MARGIN, w - MARGIN], [0, screenW])
                    rawY = np.interp(y2, [MARGIN, h - MARGIN], [0, screenH])
                    curX = prevMouseX + (rawX - prevMouseX) / MOUSE_SMOOTH
                    curY = prevMouseY + (rawY - prevMouseY) / MOUSE_SMOOTH
                    pyautogui.moveTo(curX, curY)
                    prevMouseX, prevMouseY = curX, curY

                    cv2.line(img, (x1, y1), (x2, y2), (180, 0, 255), 2)

                    if pinchLen < PINCH_DIST:
                        mid = ((x1 + x2) // 2, (y1 + y2) // 2)
                        cv2.circle(img, mid, 18, (0, 255, 80), cv2.FILLED)
                        cv2.circle(img, mid, 18, (255, 255, 255), 2)
                        mode = "MOUSE  [ CLICK ]"
                        if now - lastClickTime > CLICK_CD:
                            pyautogui.click()
                            lastClickTime = now

                # ════════════════════════════════════════
                #  2 FINGERS → SCROLL
                #  Move hand UP   = scroll up
                #  Move hand DOWN = scroll down
                # ════════════════════════════════════════
                elif totalFingers == 2 and gestureReady:
                    mode = "SCROLL"

                    handY = (indexTip[2] + midTip[2]) // 2
                    handX = (indexTip[1] + midTip[1]) // 2

                    if prevHandY is None:
                        prevHandY = handY

                    deltaY = prevHandY - handY  # positive = hand moved UP

                    if abs(deltaY) > 2:  # ignore tiny jitter
                        pyautogui.scroll(int(np.sign(deltaY) * SCROLL_SPEED))

                    prevHandY = handY

                    # draw fingertip dots + direction arrow
                    sc = (0, 220, 255)
                    cv2.circle(img, (indexTip[1], indexTip[2]), 11, sc, cv2.FILLED)
                    cv2.circle(img, (midTip[1], midTip[2]), 11, sc, cv2.FILLED)
                    arrow_end = (handX, handY - 45 if deltaY > 0 else handY + 45)
                    cv2.arrowedLine(
                        img, (handX, handY), arrow_end, sc, 3, tipLength=0.4
                    )

                # ════════════════════════════════════════
                #  3 FINGERS → VOLUME
                #  Raise hand HIGH  = LOUDER
                #  Lower hand DOWN  = QUIETER
                #  (tracks wrist position, no pinching needed)
                # ════════════════════════════════════════
                elif totalFingers == 3 and volumeEnabled:

                    wristY = wrist[2]  # small Y = high on screen = loud

                    # map wrist Y → volume % (inverted so UP = louder)
                    rawPct = int(np.interp(wristY, [MARGIN, h - MARGIN], [100, 0]))
                    rawPct = max(0, min(100, rawPct))

                    # smooth so bar doesn't jump
                    smoothVolPct += (rawPct - smoothVolPct) / VOL_SMOOTH
                    displayPct = int(smoothVolPct)

                    # set system volume
                    volDb = float(np.interp(smoothVolPct, [0, 100], [minVol, maxVol]))
                    volume.SetMasterVolumeLevel(volDb, None)

                    mode = f"VOLUME  {displayPct}%"
                    vc = vol_color(displayPct)

                    # ── wrist dot + level line (position feedback) ──
                    cv2.line(img, (MARGIN, wristY), (w - MARGIN, wristY), vc, 2)
                    cv2.circle(img, (wrist[1], wristY), 16, vc, cv2.FILLED)
                    cv2.circle(img, (wrist[1], wristY), 16, (255, 255, 255), 2)

                    # ── BIG CENTERED VOLUME BAR ─────────────────────
                    # background track
                    bar_x, bar_y = w // 2 - 20, 80
                    bar_w, bar_h = 40, h - 160
                    filled_h = int(bar_h * displayPct / 100)
                    fill_y = bar_y + bar_h - filled_h

                    # dark track
                    cv2.rectangle(
                        img,
                        (bar_x, bar_y),
                        (bar_x + bar_w, bar_y + bar_h),
                        (30, 30, 30),
                        -1,
                    )
                    # filled portion
                    cv2.rectangle(
                        img,
                        (bar_x, fill_y),
                        (bar_x + bar_w, bar_y + bar_h),
                        vc,
                        cv2.FILLED,
                    )
                    # white border
                    cv2.rectangle(
                        img,
                        (bar_x, bar_y),
                        (bar_x + bar_w, bar_y + bar_h),
                        (200, 200, 200),
                        2,
                    )

                    # HUGE % number centred below the bar
                    big_lbl = f"{displayPct}%"
                    fs = 2.2
                    thick = 4
                    (tw, th), _ = cv2.getTextSize(
                        big_lbl, cv2.FONT_HERSHEY_SIMPLEX, fs, thick
                    )
                    tx = (w - tw) // 2
                    ty = bar_y + bar_h + th + 12
                    # shadow
                    cv2.putText(
                        img,
                        big_lbl,
                        (tx + 2, ty + 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        fs,
                        (0, 0, 0),
                        thick + 2,
                        cv2.LINE_AA,
                    )
                    # main text
                    cv2.putText(
                        img,
                        big_lbl,
                        (tx, ty),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        fs,
                        (255, 255, 255),
                        thick,
                        cv2.LINE_AA,
                    )

                    # hint arrows above / below bar
                    lbl(img, "RAISE = LOUDER", (bar_x - 90, bar_y - 10), 0.45, vc)
                    lbl(
                        img,
                        "LOWER = QUIETER",
                        (bar_x - 90, bar_y + bar_h + 14),
                        0.45,
                        vc,
                    )

                elif totalFingers == 3 and not volumeEnabled:
                    mode = "VOLUME N/A"
                elif totalFingers not in (0, 1, 2, 3):
                    mode = "IDLE"

            # always draw thumb + index dots
            cv2.circle(img, (x1, y1), 8, (255, 0, 200), cv2.FILLED)
            cv2.circle(img, (x2, y2), 8, (0, 200, 255), cv2.FILLED)

    else:
        prevHandY = None  # reset when hand leaves frame

    # ── ACTIVE ZONE BORDER ────────────────────────────
    border_col = (0, 210, 0) if systemActive else (0, 0, 210)
    cv2.rectangle(img, (MARGIN, MARGIN), (w - MARGIN, h - MARGIN), border_col, 1)

    # ── FPS ───────────────────────────────────────────
    currTime = time.time()
    fps = 1 / (currTime - prevTime) if (currTime - prevTime) > 0 else 0
    prevTime = currTime

    # ── HUD PANEL ─────────────────────────────────────
    panel(img, 8, 8, 282, 215)

    sc = (0, 220, 0) if systemActive else (60, 60, 220)
    ss = "ACTIVE" if systemActive else "LOCKED"
    lbl(img, f"STATUS : {ss}", (18, 34), 0.60, sc, thick=2)
    lbl(img, f"MODE   : {mode}", (18, 58), 0.58, (220, 220, 0))
    lbl(img, f"FPS    : {int(fps)}", (18, 80), 0.50, (140, 140, 140))

    lbl(img, "GESTURES ──────────────────────", (18, 102), 0.40, (85, 85, 85))
    lbl(img, " FIST   ->  Lock / Unlock", (18, 119), 0.42, (135, 135, 135))
    lbl(img, " 1 FIN  ->  Move Mouse", (18, 135), 0.42, (135, 135, 135))
    lbl(img, " PINCH  ->  Left Click", (18, 151), 0.42, (135, 135, 135))
    lbl(img, " 2 FIN  ->  Scroll  (up/down)", (18, 167), 0.42, (135, 135, 135))
    lbl(img, " 3 FIN  ->  Volume  (up=loud)", (18, 183), 0.42, (135, 135, 135))
    lbl(img, " Q key  ->  Quit", (18, 199), 0.42, (135, 135, 135))

    cv2.imshow("SynapseOS Lite", img)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
