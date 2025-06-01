import socket
import json
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import pandas as pd

import matplotlib
matplotlib.use('TkAgg')

UDP_PORT = 8080
BUFFER_SIZE = 1024

trajectory_points = []

# === Receive UDP Messages ===
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', UDP_PORT))
print(f"[UDP] Listening on port {UDP_PORT}...")

while True:
    data, _ = sock.recvfrom(BUFFER_SIZE)
    try:
        decoded = json.loads(data.decode())
        print(decoded)
        msg_type = decoded.get("type")
        if msg_type == "latent":
            point = decoded.get("message", {}).get("data", [])
            if len(point) == 3:
                trajectory_points.append(tuple(map(float, point)))
        elif msg_type == "start_latent_viz":
            print("[UDP] Received start_viz. Plotting...")
            break
    except Exception as e:
        print(f"[UDP] Error: {e}")

# === Plot Once ===
if trajectory_points:
    ls_3D_path = '/Users/tomasandrade/Documents/BSC/ICHOIR/Applio_light/assets/features/embedding_n100_3D.csv'
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


    xs, ys, zs = zip(*trajectory_points)
    #fig = plt.figure()
    #ax = fig.add_subplot(111, projection='3d')
    ax.scatter(xs, ys, zs, c='red')
    ax.set_title("Received Trajectory")
    plt.show()
else:
    print("No points received.")
