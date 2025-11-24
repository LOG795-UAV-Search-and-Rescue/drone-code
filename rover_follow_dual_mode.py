import socket, json, math, select
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# =====================================================
# CONFIGURATION
# =====================================================
DRONE_PORT = 5005               # incoming from drone + UI commands
INTERFACE_IP = "127.0.0.1"      # sim receiver for rover commands
INTERFACE_PORT = 8000

Kt = 0.8
Kr = 1.2
STOP_DIST = 0.05
VISUAL_SCALE = 2.0
QUALITY_MIN = 30.0

# =====================================================
# STATE
# =====================================================
rover_x = rover_y = 0.0
drone_x = drone_y = 0.0
quality = 100.0

last_good_x = last_good_y = 0.0
reset_pending = False
under_drone = True

MODE_CONTINUOUS = True
MODE_WAIT = False
cmd_triggered = False

manual_target = {"active": False, "x": 0.0, "y": 0.0}

# Networking
recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("0.0.0.0", DRONE_PORT))

send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"[PC] Listening on UDP {DRONE_PORT}")
print(f"[PC] Sending rover cmds to {INTERFACE_IP}:{INTERFACE_PORT}\n")

# =====================================================
# VISUAL SETUP
# =====================================================
fig, ax = plt.subplots()
ax.set_xlim(-VISUAL_SCALE, VISUAL_SCALE)
ax.set_ylim(-VISUAL_SCALE, VISUAL_SCALE)
ax.set_title("Drone → Rover Simulation")
ax.set_xlabel("X m")
ax.set_ylabel("Y m")

drone_dot, = ax.plot([], [], 'bo', label="Drone")
rover_dot, = ax.plot([], [], 'ro', label="Rover")
ax.legend()

# =====================================================
# RECEIVE DATA OR COMMANDS
# =====================================================
def receive_drone_data():
    global drone_x, drone_y, quality
    global last_good_x, last_good_y
    global MODE_CONTINUOUS, MODE_WAIT, cmd_triggered
    global reset_pending, under_drone
    global manual_target

    try:
        recv_sock.setblocking(0)

        while True:
            ready, _, _ = select.select([recv_sock], [], [], 0)
            if not ready:
                break

            data, _ = recv_sock.recvfrom(1024)
            msg = data.decode(errors="ignore").strip()

            # -------------------------------------------
            # GOTO COMMAND FROM UI
            # -------------------------------------------
            if msg.startswith("GOTO"):
                try:
                    _, xs, ys = msg.split()
                    gx = float(xs)
                    gy = float(ys)

                    manual_target["active"] = True
                    manual_target["x"] = gx
                    manual_target["y"] = gy

                    MODE_CONTINUOUS = False
                    MODE_WAIT = False
                    cmd_triggered = False

                    print(f"[GOTO] New target → ({gx}, {gy})")
                except Exception as e:
                    print("[GOTO ERROR]", msg, e)

                continue

            # -------------------------------------------
            # MODE COMMANDS
            # -------------------------------------------
            if msg == "MODE_CONTINUOUS":
                MODE_CONTINUOUS = True
                MODE_WAIT = False
                manual_target["active"] = False
                cmd_triggered = False
                print("[MODE] FOLLOW MODE")
                continue

            if msg == "MODE_COME_TO_ME":
                MODE_CONTINUOUS = False
                MODE_WAIT = True
                manual_target["active"] = False
                cmd_triggered = False
                print("[MODE] WAIT MODE")
                continue

            if msg == "CMD_COME_TO_ME":
                cmd_triggered = True
                manual_target["active"] = False
                print("[CMD] COME-TO-ME TRIGGERED")
                continue

            # -------------------------------------------
            # POSE PACKETS FROM DRONE
            # Format: ts,x,y,q
            # -------------------------------------------
            parts = msg.split(",")
            if len(parts) < 4:
                continue

            ts, xs, ys, qs = parts[:4]
            x = float(xs)
            y = float(ys)
            q = float(qs)

            if q < QUALITY_MIN:
                quality = q
                print(f"[WARN] Low VIO q={q}, holding last good")
                continue

            drone_x = x
            drone_y = y
            quality = q

            last_good_x = x
            last_good_y = y

    except Exception as e:
        print("[ERROR recv]", e)

# =====================================================
# ROVER CONTROL LOGIC
# =====================================================
def control_rover():
    global rover_x, rover_y, cmd_triggered, manual_target

    # --- If a GOTO target is active, override everything ---
    if manual_target["active"]:
        tx = manual_target["x"]
        ty = manual_target["y"]

        dx = tx - rover_x
        dy = ty - rover_y
        dist = math.sqrt(dx*dx + dy*dy)

        if dist < STOP_DIST:
            print("[GOTO] Target reached.")
            manual_target["active"] = False
            send_cmd(0,0,0)
            return

        T = max(min(Kt * dy, 1), -1)
        A = max(min(Kr * dx, 1), -1)

        L = max(min(T - A, 1), -1)
        R = max(min(T + A, 1), -1)

        send_cmd(T, L, R)

        rover_x += 0.1 * dx
        rover_y += 0.1 * dy
        return

    # --- COME-TO-ME MODE ---
    if MODE_WAIT and not cmd_triggered:
        send_cmd(0,0,0)
        return

    # Determine target
    if cmd_triggered:
        tx, ty = last_good_x, last_good_y
    elif MODE_CONTINUOUS:
        tx, ty = drone_x, drone_y
    else:
        tx, ty = rover_x, rover_y

    dx = tx - rover_x
    dy = ty - rover_y
    dist = math.sqrt(dx*dx + dy*dy)

    if dist < STOP_DIST:
        if cmd_triggered:
            print("[INFO] COME-TO-ME completed")
            cmd_triggered = False
        send_cmd(0,0,0)
        return

    T = max(min(Kt * dy, 1), -1)
    A = max(min(Kr * dx, 1), -1)

    L = max(min(T - A, 1), -1)
    R = max(min(T + A, 1), -1)

    send_cmd(T, L, R)

    rover_x += 0.1 * dx
    rover_y += 0.1 * dy

# =====================================================
# SENDER
# =====================================================
def send_cmd(T,L,R):
    cmd = {"T":round(T,3), "L":round(L,3), "R":round(R,3)}
    send_sock.sendto(json.dumps(cmd).encode(), (INTERFACE_IP, INTERFACE_PORT))
    print(f"[CMD] {cmd}")

# =====================================================
# UI LOOP
# =====================================================
def update(frame):
    receive_drone_data()
    control_rover()

    drone_dot.set_data([drone_x], [drone_y])
    drone_dot.set_color("gray" if quality < QUALITY_MIN else "blue")

    rover_dot.set_data([rover_x], [rover_y])
    rover_dot.set_color("red" if not manual_target["active"] else "cyan")

    return drone_dot, rover_dot

ani = FuncAnimation(fig, update, interval=100, cache_frame_data=False)
plt.show()
