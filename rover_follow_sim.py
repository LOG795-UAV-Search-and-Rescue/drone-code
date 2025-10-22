import socket
import json
import math
import select
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# =====================================================
# CONFIGURATION
# =====================================================
DRONE_PORT = 5005
INTERFACE_IP = "127.0.0.1"
INTERFACE_PORT = 8000

Kt = 0.8
Kr = 1.2
STOP_DIST = 0.05
VISUAL_SCALE = 2.0

# =====================================================
# INITIAL STATE
# =====================================================
rover_x, rover_y = 0.0, 0.0
drone_x, drone_y = 0.0, 0.0
quality = 0.0

recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("0.0.0.0", DRONE_PORT))
send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"[PC] Listening for drone VIO data on port {DRONE_PORT}")
print(f"[PC] Sending rover JSON commands to {INTERFACE_IP}:{INTERFACE_PORT}\n")

# =====================================================
# VISUALIZATION
# =====================================================
fig, ax = plt.subplots()
ax.set_xlim(-VISUAL_SCALE, VISUAL_SCALE)
ax.set_ylim(-VISUAL_SCALE, VISUAL_SCALE)
ax.set_xlabel("X (m)")
ax.set_ylabel("Y (m)")
ax.set_title("Drone–Rover Follow Simulation")
drone_dot, = ax.plot([], [], 'bo', label="Drone")
rover_dot, = ax.plot([], [], 'ro', label="Rover")
ax.legend()

# =====================================================
# RECEIVE DRONE DATA (ROBUST)
# =====================================================
def receive_drone_data():
    """Read *latest* drone VIO packet, discarding older ones if backlog exists."""
    global drone_x, drone_y, quality
    try:
        recv_sock.setblocking(0)
        latest_msg = None

        # Drain the socket buffer completely
        while True:
            ready, _, _ = select.select([recv_sock], [], [], 0)
            if not ready:
                break
            data, _ = recv_sock.recvfrom(1024)
            latest_msg = data

        # Parse only the latest valid packet
        if latest_msg is None:
            return

        msg = latest_msg.decode(errors="ignore").strip()
        lines = msg.split("\n")
        last_line = lines[-1].strip()
        parts = last_line.split(",")

        if len(parts) < 4:
            return

        ts, xd, yd, q = parts[:4]
        drone_x = float(xd)
        drone_y = float(yd)
        quality = float(q) if q.replace('.', '', 1).isdigit() else 0.0

    except Exception as e:
        print("[ERROR receiving data]", e)

# =====================================================
# CONTROL ROVER
# =====================================================
def control_rover():
    global rover_x, rover_y, drone_x, drone_y

    dx = drone_x - rover_x
    dy = drone_y - rover_y
    dist = math.sqrt(dx**2 + dy**2)

    if dist < STOP_DIST:
        T = L = R = 0.0
    else:
        T = max(min(Kt * dy, 1.0), -1.0)
        angular = max(min(Kr * dx, 1.0), -1.0)
        L = max(min(T - angular, 1.0), -1.0)
        R = max(min(T + angular, 1.0), -1.0)

    cmd = {"T": round(T, 3), "L": round(L, 3), "R": round(R, 3)}
    send_sock.sendto(json.dumps(cmd).encode(), (INTERFACE_IP, INTERFACE_PORT))

    print(f"[CMD] {cmd} | Drone=({drone_x:.3f}, {drone_y:.3f}) | Q={quality:.0f}")

    # Simulate rover motion
    step = 0.1
    rover_x += step * (drone_x - rover_x)
    rover_y += step * (drone_y - rover_y)

# =====================================================
# ANIMATION
# =====================================================
def update(frame):
    receive_drone_data()
    control_rover()

    drone_dot.set_data([drone_x], [drone_y])
    rover_dot.set_data([rover_x], [rover_y])
    return drone_dot, rover_dot

ani = FuncAnimation(fig, update, interval=100, cache_frame_data=False)
plt.show()
