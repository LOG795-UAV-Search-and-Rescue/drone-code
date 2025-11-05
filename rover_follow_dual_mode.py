import socket, json, math, select
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# =====================================================
# CONFIGURATION
# =====================================================
DRONE_PORT = 5005
INTERFACE_IP = "127.0.0.1"
INTERFACE_PORT = 8000  # UI SIM PORT

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

# Modes
MODE_CONTINUOUS = True   # default
MODE_WAIT = False
cmd_triggered = False    # true when SPACE pressed on drone

# Networking
recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind(("0.0.0.0", DRONE_PORT))
send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"[PC] Listening for drone data on UDP {DRONE_PORT}")
print(f"[PC] Sending rover sim cmds to {INTERFACE_IP}:{INTERFACE_PORT}\n")

# =====================================================
# VISUAL SETUP
# =====================================================
fig, ax = plt.subplots()
ax.set_xlim(-VISUAL_SCALE, VISUAL_SCALE)
ax.set_ylim(-VISUAL_SCALE, VISUAL_SCALE)
ax.set_title("Drone → Rover Dual-Mode System")
ax.set_xlabel("X m")
ax.set_ylabel("Y m")

drone_dot, = ax.plot([], [], 'bo', label="Drone")
rover_dot, = ax.plot([], [], 'ro', label="Rover")
ax.legend()

# =====================================================
# RECEIVE DATA
# =====================================================
def receive_drone_data():
    global drone_x, drone_y, quality, last_good_x, last_good_y
    global MODE_CONTINUOUS, MODE_WAIT, cmd_triggered
    global reset_pending, under_drone

    try:
        recv_sock.setblocking(0)
        # Drain all pending UDP packets each frame
        while True:
            ready, _, _ = select.select([recv_sock], [], [], 0)
            if not ready:
                break

            data, _ = recv_sock.recvfrom(1024)
            msg = data.decode(errors="ignore").strip()

            # ---------------------
            # MODE COMMANDS
            # ---------------------
            if msg == "MODE_CONTINUOUS":
                MODE_CONTINUOUS, MODE_WAIT = True, False
                cmd_triggered = False
                print("[MODE] FOLLOW MODE")
                continue  # <-- keep draining, don't return

            if msg == "MODE_COME_TO_ME":
                MODE_CONTINUOUS, MODE_WAIT = False, True
                cmd_triggered = False
                print("[MODE] WAIT MODE — waiting for trigger")
                continue  # <-- keep draining, don't return

            if msg == "CMD_COME_TO_ME":
                cmd_triggered = True
                print("[CMD] COME-TO-ME TRIGGERED")
                continue  # one-shot command, keep draining

            # ---------------------
            # POSITION DATA
            # Accept 4- or 5-field packets:
            #   ts,x,y,q           (no reset flag)
            #   ts,x,y,q,resetflag (optional)
            # ---------------------
            parts = msg.split(",")
            if len(parts) < 4:
                continue  # not a pose packet

            if len(parts) >= 5:
                ts, xs, ys, qs, reset_flag = parts[:5]
            else:
                ts, xs, ys, qs = parts[:4]
                reset_flag = "0"

            # Parse
            x = float(xs)
            y = float(ys)
            q = float(qs)

            # Quality filter
            if q < QUALITY_MIN:
                # hold last good position but still update quality
                quality = q
                print(f"[WARN] Bad VIO q={q:.0f}, holding last good position")
                continue

            # Accept new good pose
            drone_x, drone_y, quality = x, y, q
            last_good_x, last_good_y = x, y

            # Optional reset handling if you later add it on the drone
            if reset_flag == "1" and not reset_pending:
                reset_pending = True
                under_drone = False
                print("[INFO] VIO reset detected — syncing")

    except Exception as e:
        print("[ERROR recv]", e)


# =====================================================
# CONTROL LOGIC
# =====================================================
def control_rover():
    global rover_x, rover_y, cmd_triggered, reset_pending, under_drone

    # HOLD in WAIT mode until trigger
    if MODE_WAIT and not cmd_triggered and not reset_pending:
        send_cmd(0,0,0)
        return

    # Determine target
    if cmd_triggered:
        tx, ty = last_good_x, last_good_y
    elif MODE_CONTINUOUS:
        tx, ty = drone_x, drone_y
    else:
        tx, ty = rover_x, rover_y  # should not move

    dx, dy = tx - rover_x, ty - rover_y
    dist = math.sqrt(dx*dx + dy*dy)

    # Arrived case
    if dist < STOP_DIST:
        if cmd_triggered:
            print("[INFO] Arrived — completing come-to-me")
            cmd_triggered = False
        send_cmd(0,0,0)
        return

    # PID / P-control
    T = max(min(Kt * dy, 1), -1)
    A = max(min(Kr * dx, 1), -1)
    L = max(min(T - A, 1), -1)
    R = max(min(T + A, 1), -1)

    send_cmd(T,L,R)

    rover_x += 0.1 * dx
    rover_y += 0.1 * dy

# =====================================================
# SENDER
# =====================================================
def send_cmd(T,L,R):
    cmd = {"T":round(T,3), "L":round(L,3), "R":round(R,3)}
    send_sock.sendto(json.dumps(cmd).encode(), (INTERFACE_IP, INTERFACE_PORT))
    print(f"[CMD] {cmd}  | Mode={'FOLLOW' if MODE_CONTINUOUS else 'WAIT'}  | Trigger={cmd_triggered}")

# =====================================================
# UI LOOP
# =====================================================
def update(frame):
    receive_drone_data()
    control_rover()

    # Plot drone
    drone_dot.set_data([drone_x], [drone_y])
    drone_dot.set_color("gray" if quality < QUALITY_MIN else "blue")

    # Plot rover
    color = "green" if MODE_WAIT else "red"
    if reset_pending and not under_drone:
        color = "yellow"
    rover_dot.set_color(color)
    rover_dot.set_data([rover_x], [rover_y])

    return drone_dot, rover_dot

ani = FuncAnimation(fig, update, interval=100, cache_frame_data=False)
plt.show()
