import socket
import json
import math
import select
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# =====================================================
# CONFIG
# =====================================================
DRONE_PORT = 5005
INTERFACE_IP = "127.0.0.1"
INTERFACE_PORT = 8000

Kt = 0.8
Kr = 1.2
STOP_DIST = 0.05
VISUAL_SCALE = 2.0
QUALITY_MIN = 30.0   # When QUALITY IS LOW Localization = bad, IGNORE DATA

# =====================================================
# INITIAL STATE OF THE POSITIONNING OF THE DRONE AND ROVER
# =====================================================
rover_x, rover_y = 0.0, 0.0
drone_x, drone_y = 0.0, 0.0
quality = 100.0

reset_pending = False
under_drone = True
last_drone_x, last_drone_y = 0.0, 0.0
last_good_x, last_good_y = 0.0, 0.0   # When the QUALITY GOES BAD we save THE LAST RECORDED GOOD POSITION TO GO TO IT

recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("0.0.0.0", DRONE_PORT))
send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"[PC] Listening for drone VIO data on port {DRONE_PORT}")
print(f"[PC] Sending rover JSON commands to {INTERFACE_IP}:{INTERFACE_PORT}\n")

# =====================================================
# FOR UI JUST IGNORE
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
# HERE LOOP FOR US TO RECEIVE THE DATA FROM THE DRONE
# =====================================================
def receive_drone_data():
    """
    Receives and filters drone VIO data.
    - Ignores low-quality updates.
    - Keeps last stable position for continuity.
    - Handles reset detection.
    """
    global drone_x, drone_y, quality
    global reset_pending, under_drone, last_drone_x, last_drone_y, last_good_x, last_good_y

    try:
        recv_sock.setblocking(0)
        latest_msg = None

        while True:
            ready, _, _ = select.select([recv_sock], [], [], 0)
            if not ready:
                break
            data, _ = recv_sock.recvfrom(1024)
            latest_msg = data

        if latest_msg is None:
            return

        msg = latest_msg.decode(errors="ignore").strip()
        last_line = msg.split("\n")[-1].strip()
        parts = last_line.split(",")

        # Expected format: ts, x, y, q, reset_flag
        if len(parts) < 5:
            return

        ts, xd, yd, q, reset_flag = parts[:5]
        x, y = float(xd), float(yd)
        q = float(q)

        # --- Quality filtering ---
        if q < QUALITY_MIN:
            # Here we will ignore the positions with bad quality BECAUSE THEYRE NOT GOOD POSITIONS TO WE SAVE THE LAST GOOD POSITIONS
            print(f"[WARN] Low quality ({q:.0f}) → ignoring noisy data.")
            drone_x, drone_y = last_good_x, last_good_y
            quality = q
            return
        else:
            # Otherwise we will store the new good positions here
            drone_x, drone_y, quality = x, y, q
            last_good_x, last_good_y = x, y

        # --- When quality is =0 the drone resets its position to 0,0, we have to detect it and then send the good positionning the rover ---
        if reset_flag == "1" and not reset_pending:
            print("[INFO] Drone reset detected — keeping rover on last valid position.")
            reset_pending = True
            under_drone = False
            # the rover will go the last good position recorded before the reset
            last_drone_x, last_drone_y = last_good_x, last_good_y

    except Exception as e:
        print("[ERROR receiving data]", e)


# =====================================================
# LOGIC TO CONTROL ROVER
# =====================================================
def control_rover():
    """
    Proportional controller for rover following logic.
    Includes graceful reset completion and stable low-quality behavior.  
    """
    global rover_x, rover_y, reset_pending, under_drone

    # --- Follow logic ---
    if not reset_pending:
        dx = drone_x - rover_x
        dy = drone_y - rover_y
    else:
        dx = last_drone_x - rover_x
        dy = last_drone_y - rover_y

    dist = math.sqrt(dx**2 + dy**2)

    # --- Motor control ---
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

    # --- Simulate rover motion ---
    step = 0.1
    rover_x += step * dx
    rover_y += step * dy

    # --- Graceful reset handling ---
    if reset_pending and not under_drone:
        dist_to_last = math.sqrt((rover_x - last_drone_x)**2 + (rover_y - last_drone_y)**2)
        if dist_to_last < STOP_DIST:
            print("[SYNC] Rover reached last valid drone position — resetting to (0,0).")
            rover_x, rover_y = 0.0, 0.0
            under_drone = True
            reset_pending = False


# =====================================================
# ANIMATION LOOP
# =====================================================
def update(frame):
    receive_drone_data()
    control_rover()

    # --- Update drone position ---
    drone_dot.set_data([drone_x], [drone_y])

    # --- Color logic ---
    if quality < QUALITY_MIN:
        drone_dot.set_color("gray")      # Low-quality visual
    else:
        drone_dot.set_color("blue")      # Normal VIO tracking

    if reset_pending and not under_drone:
        rover_dot.set_color("yellow")    # Graceful reset phase
    else:
        rover_dot.set_color("red")       # Normal operation

    # --- Update rover position ---
    rover_dot.set_data([rover_x], [rover_y])
    return drone_dot, rover_dot


ani = FuncAnimation(fig, update, interval=100, cache_frame_data=False)
plt.show()
