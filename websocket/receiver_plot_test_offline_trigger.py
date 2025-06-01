import socket
import threading
import json
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation as animation

trajectory_points = []
start_animation = threading.Event()

UDP_PORT = 5005

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
    print(f"Listening for UDP on port {UDP_PORT}...")

    while True:
        data, _ = sock.recvfrom(4096)
        try:
            msg = json.loads(data.decode().strip())
            msg_type = msg.get("type")

            if msg_type == "latent":
                point = msg.get("message", {}).get("data")
                if point and len(point) == 3:
                    trajectory_points.append(tuple(point))
                else:
                    print(f"Ignoring malformed trajectory data: {msg}")
            elif msg_type == "start_latent_viz":
                print("Received start_viz signal.")
                start_animation.set()
            else:
                print(f"Unknown message type: {msg_type}")
        except json.JSONDecodeError:
            print("Received invalid JSON.")

def animate(i, line, ax):
    if i >= len(trajectory_points):
        return
    xs, ys, zs = zip(*trajectory_points[:i+1])
    line.set_data(xs, ys)
    line.set_3d_properties(zs)

def run_animation():
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    line, = ax.plot([], [], [], lw=2)

    # Optionally adjust limits based on your data
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_zlim(-10, 10)

    ani = animation.FuncAnimation(fig, animate, fargs=(line, ax),
                                  frames=len(trajectory_points), interval=100, repeat=False)
    plt.show()

if __name__ == "__main__":
    threading.Thread(target=udp_listener, daemon=True).start()
    print("Waiting for start_viz signal to animate...")
    start_animation.wait()
    run_animation()
