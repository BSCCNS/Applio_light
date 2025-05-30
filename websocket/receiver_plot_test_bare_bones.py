import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.set_xlim([0, 10])
ax.set_ylim([0, 10])
ax.set_zlim([0, 10])

# Dummy scatter
scatter = ax.scatter([], [], [], s=30, c='red')

# Coordinate label at the bottom of the figure
coord_label = fig.text(0.5, 0.02, "(waiting for data...)", ha='center', fontsize=14, color='black')

# Dummy data buffer
points = [(i, i, i) for i in range(50)]

def update(frame):
    x, y, z = points[frame]
    scatter._offsets3d = ([x], [y], [z])
    coord_label.set_text(f"({x:.2f}, {y:.2f}, {z:.2f})")
    return scatter, coord_label

ani = FuncAnimation(fig, update, frames=len(points), interval=200, blit=False)
plt.show()
