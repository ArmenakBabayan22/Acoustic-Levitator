import cv2
import mediapipe as mp
import serial
import serial.tools.list_ports
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import threading
import matplotlib
matplotlib.rcParams['figure.facecolor'] = 'black'
matplotlib.rcParams['axes.facecolor'] = 'black'
matplotlib.rcParams['text.color'] = 'white'
matplotlib.rcParams['axes.labelcolor'] = 'white'
matplotlib.rcParams['xtick.color'] = 'white'
matplotlib.rcParams['ytick.color'] = 'white'

def find_port():
    for p in serial.tools.list_ports.comports():
        if any(x in p.description for x in ['Arduino','CH340','USB']):
            return p.device
    ports = serial.tools.list_ports.comports()
    return ports[0].device if ports else 'COM3'

try:
    ser = serial.Serial(find_port(), 9600, timeout=0.05)
    ser.flushInput()
    connected = True
except:
    connected = False

BASE_FREQ = 197
MAX_UP    = 10
MAX_DOWN  = 10
state = {
    'ocr1a':   BASE_FREQ,
    'hand_y':  0.5,
    'hand_ok': False,
}

mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils

def hand_thread():
    cap = cv2.VideoCapture(1)
    with mp_hands.Hands(max_num_hands=1,
                        min_detection_confidence=0.7,
                        min_tracking_confidence=0.7) as hands:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res   = hands.process(rgb)

            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0]
                hy = lm.landmark[0].y
                state['hand_y']  = hy
                state['hand_ok'] = True
                new_ocr = int(BASE_FREQ + (hy - 0.5) * (MAX_DOWN + MAX_UP))
                new_ocr = max(BASE_FREQ - MAX_UP, min(BASE_FREQ + MAX_DOWN, new_ocr))
                state['ocr1a'] = new_ocr
                if connected:
                    ser.write(f"SET:{new_ocr}\n".encode())
                mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)
                cv2.putText(frame, f"OCR1A: {new_ocr}  freq: {16000000//(2*new_ocr)} Hz",
                            (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,200), 2)
            else:
                state['hand_ok'] = False
                cv2.putText(frame, "Show your hand!", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,100,255), 2)

            cv2.imshow("Hand Control", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    cap.release()
    cv2.destroyAllWindows()

t = threading.Thread(target=hand_thread, daemon=True)
t.start()

c        = 343
distance = 0.10
x  = np.linspace(-0.04, 0.04, 120)
z  = np.linspace(0.01,  0.09, 120)
X, Z = np.meshgrid(x, z)

N      = 32
angles = np.linspace(0, 2*np.pi, N, endpoint=False)
r      = 0.05
R_bottom = [np.sqrt((X - r*np.cos(a))**2 + Z**2           + 1e-10) for a in angles]
R_top    = [np.sqrt((X - r*np.cos(a))**2 + (Z-distance)**2 + 1e-10) for a in angles]

sim_t        = [0]
history_freq = [40609] * 50
pos_history  = [5.0]   * 10

fig = plt.figure(figsize=(14, 9))
fig.patch.set_facecolor('black')

ax = fig.add_axes([0.04, 0.08, 0.50, 0.86])
ax.set_facecolor('black')
ax.set_xlabel('X (cm)')
ax.set_ylabel('Z (cm)')
for sp in ax.spines.values(): sp.set_edgecolor('gray')
im = ax.imshow(np.zeros((120,120)), extent=[-4,4,1,9],
               origin='lower', cmap='inferno', vmin=-1, vmax=1, aspect='auto')
cbar = plt.colorbar(im, ax=ax, label='Pressure', shrink=0.9)
cbar.ax.yaxis.label.set_color('white')
cbar.ax.tick_params(colors='white')
title  = ax.set_title('Waiting...', color='yellow')
status = ax.text(0.5, 1.02, '● DISCONNECTED', transform=ax.transAxes,
                 color='red', ha='center', fontsize=11)

ax_freq = fig.add_axes([0.62, 0.55, 0.35, 0.35])
ax_freq.set_facecolor('#111111')
ax_freq.set_title('Frequency (Hz)')
for sp in ax_freq.spines.values(): sp.set_edgecolor('gray')
line_freq, = ax_freq.plot(history_freq, color='orange', linewidth=2)
val_freq = ax_freq.text(0.05, 0.82, '40609 Hz', transform=ax_freq.transAxes,
                        color='orange', fontsize=14, fontweight='bold')

ax_pos = fig.add_axes([0.62, 0.08, 0.35, 0.35])
ax_pos.set_facecolor('#111111')
ax_pos.set_title('Object Position  |  Hand')
ax_pos.set_xlim(-1, 1)
ax_pos.set_ylim(1, 9)
ax_pos.set_ylabel('Z (cm)')
ax_pos.set_xticks([])
for sp in ax_pos.spines.values(): sp.set_edgecolor('gray')
ax_pos.axhline(y=1, color='cyan', linewidth=3, alpha=0.4)
ax_pos.axhline(y=9, color='cyan', linewidth=3, alpha=0.4)
obj_point, = ax_pos.plot([0], [5], 'o', color='white',
                          markersize=18, markeredgecolor='cyan', markeredgewidth=2)
obj_trail, = ax_pos.plot([0]*10, pos_history, '-', color='cyan', alpha=0.3, linewidth=2)
hand_line  = ax_pos.axhline(y=5, color='lime', linewidth=2,
                              linestyle='--', alpha=0.7, label='Hand')
ax_pos.legend(loc='upper right', fontsize=8)

def animate(frame):
    if connected:
        try:
            while ser.in_waiting > 0:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
                if 'FREQ:' in raw:
                    val = raw.split('FREQ:')[1].strip()
                    if val.isdigit():
                        state['ocr1a'] = int(val)
        except:
            pass

    ocr1a     = state['ocr1a']
    cur_freq  = 16000000 / (2 * ocr1a)
    cur_k     = 2 * np.pi * cur_freq / c
    cur_omega = 2 * np.pi * cur_freq
    sim_t[0] += 1.0 / (cur_freq * 20)

    pressure = np.zeros(X.shape)
    for R in R_bottom:
        pressure += np.cos(cur_k * R - cur_omega * sim_t[0]) / (R + 0.01)
    for R in R_top:
        pressure += np.cos(cur_k * R - cur_omega * sim_t[0] + np.pi) / (R + 0.01)
    vmax = np.percentile(np.abs(pressure), 98)
    if vmax > 0:
        im.set_data(pressure)
        im.set_clim(-vmax, vmax)

    obj_z = 8.0 - (ocr1a - (BASE_FREQ - MAX_UP)) * (7.0 / (MAX_UP + MAX_DOWN))
    obj_z = max(1.5, min(8.5, obj_z))
    pos_history.append(obj_z)
    pos_history.pop(0)
    obj_point.set_data([0], [obj_z])
    obj_trail.set_data([0]*10, pos_history)

    hand_z = 9.0 - state['hand_y'] * 8.0
    hand_line.set_ydata([hand_z, hand_z])
    hand_line.set_color('lime' if state['hand_ok'] else 'red')

    history_freq.append(cur_freq)
    history_freq.pop(0)
    line_freq.set_ydata(history_freq)
    ax_freq.set_ylim(min(history_freq) - 50, max(history_freq) + 50)
    val_freq.set_text(f'{cur_freq:.0f} Hz')

    status.set_text('● CONNECTED' if connected else '● DISCONNECTED')
    status.set_color('lime' if connected else 'red')
    title.set_text(f'Frequency: {cur_freq:.0f} Hz  |  OCR1A: {ocr1a}')

    return [im, title, status, line_freq, val_freq, obj_point, obj_trail, hand_line]

ani = animation.FuncAnimation(fig, animate, interval=50,
                               blit=True, cache_frame_data=False)
fig.canvas.mpl_connect('close_event', lambda e: ser.close() if connected else None)
plt.show()
