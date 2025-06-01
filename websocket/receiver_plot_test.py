import socket
import threading
import json
import pandas as pd
from collections import deque
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation

UDP_PORT = 8080
BUFFER_SIZE = 1024
xyz_buffer = deque(maxlen=1)

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

threading.Thread(target=udp_listener, daemon=True).start()

ls_3D_path = '/Users/tomasandrade/Documents/BSC/ICHOIR/espacio-latente-maria-main/assets/diffsinger_splitted/embedding_n100_3D.csv'
df_embed_global = pd.read_csv(ls_3D_path, index_col=0)

fig = plt.figure()
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

point_scatter = ax.scatter([], [], [], s=30, color='red')

def update(frame):
    if xyz_buffer:
        x, y, z = xyz_buffer[-1]
        point_scatter._offsets3d = ([x], [y], [z])
    return point_scatter,

ani = FuncAnimation(fig, update, interval=20, blit=False)
plt.show()
