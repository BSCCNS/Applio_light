import socket
import threading
import json
import pandas as pd
from collections import deque
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation

# === Config ===
UDP_PORT = 8080
BUFFER_SIZE = 1024
TRAIL_LENGTH = 30  # number of past points to keep for the trail

# === Data buffer ===
xyz_buffer = deque(maxlen=TRAIL_LENGTH + 1)

# === UDP Listener ===
def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    print(f"Listening on UDP port {UDP_PORT}...")

    while True:
        data, _ = sock.recvfrom(BUFFER_SIZE)
        try:
            decoded = json.loads(data.decode())
            array = decoded.get("data", [])
            if len(array) >= 3:
                x, y, z = array[:3]
                xyz_buffer.append((float(x), float(y), float(z)))
        except Exception as e:
            print(f"Invalid data: {data} — {e}")

# Start UDP listener thread
threading.Thread(target=udp_listener, daemon=True).start()

ls_3D_path = '/Users/tomasandrade/Documents/BSC/ICHOIR/voice-changer-okada/server/voice_changer/RVC/projection/embedding_n100_3D.csv'
df_embed_global = pd.read_csv(ls_3D_path, index_col=0)

# === Plot setup ===
fig = plt.figure(figsize=(8,8))
coord_label = fig.text(0.5, 0.02, "", ha='center', fontsize=14, color='black')
ax = fig.add_subplot(111, projection='3d')
# ax.set_xlim(-10, 10)
# ax.set_ylim(-10, 10)
# ax.set_zlim(-10, 10)

ax.set_xlim([-1,15])
ax.set_ylim([-1,15])
ax.set_zlim([-5,5])

ax.scatter(df_embed_global['x'], 
            df_embed_global['y'], 
            df_embed_global['z'], 
            s=0.1, 
            alpha=0.075)

# Trail and current point
trail_scatter = ax.scatter([], [], [], s=10, c='red', alpha=0.3)
head_scatter = ax.scatter([], [], [], s=30, c='red')

# === Animation update ===
def update(frame):
    if not xyz_buffer:
        coord_label.set_text("(waiting for data...)")
        return trail_scatter, head_scatter, coord_label

    points = list(xyz_buffer)
    *trail, head = points

    if trail:
        trail_x, trail_y, trail_z = zip(*trail)
        trail_scatter._offsets3d = (trail_x, trail_y, trail_z)
    else:
        trail_scatter._offsets3d = ([], [], [])

    x, y, z = head
    head_scatter._offsets3d = ([x], [y], [z])
    coord_label.set_text(f"({x:.2f}, {y:.2f}, {z:.2f})")

    return trail_scatter, head_scatter, coord_label


ani = FuncAnimation(fig, update, interval=20, blit=False)
plt.show()
