import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pymavlink import mavutil

# Connect to MAVLink (drone must be streaming on UDP:14550)
master = mavutil.mavlink_connection('udp:0.0.0.0:14550')

# --- Rover Simulation Parameters ---
rover_x, rover_y = 0.0, 0.0     # Rover starts at origin
DRONE_THRESHOLD = 0.0        # how close rover must stay (meters)
ROVER_STEP = 0.1                # rover step per update (meters)

# Drone position and origin
drone_pos = [0.0, 0.0]
origin_x, origin_y = None, None

# Path history
drone_path_x, drone_path_y = [], []
rover_path_x, rover_path_y = [], []

# --- Setup Matplotlib UI ---
fig, ax = plt.subplots()
ax.set_xlim(-2, 2)   # adjust as needed
ax.set_ylim(-2, 2)
ax.set_xlabel("X (m)")
ax.set_ylabel("Y (m)")
ax.set_title("Drone (blue) and Rover (red) - Top View (X/Y)")

# Drone and Rover markers
drone_dot, = ax.plot([], [], 'bo', label="Drone")
rover_dot, = ax.plot([], [], 'rs', label="Rover")

# Path lines
drone_line, = ax.plot([], [], 'b-', alpha=0.6)
rover_line, = ax.plot([], [], 'r-', alpha=0.6)

ax.legend()

# --- Animation Update Function ---
def update(frame):
    global rover_x, rover_y, drone_pos, origin_x, origin_y

    # Get MAVLink drone position
    msg = master.recv_match(type="LOCAL_POSITION_NED", blocking=False)
    if msg:
        if origin_x is None:
            origin_x, origin_y = msg.x, msg.y  # set reference at start
        drone_pos = [msg.x - origin_x, msg.y - origin_y]  # relative to origin

    drone_x, drone_y = drone_pos

    # Save drone path
    drone_path_x.append(drone_x)
    drone_path_y.append(drone_y)

    print(f"Drone moved -> X={drone_x:.2f}, Y={drone_y:.2f}")

    # --- Rover follow logic ---
    rover_moved = False
    if abs(drone_x - rover_x) > DRONE_THRESHOLD:
        rover_x += ROVER_STEP if drone_x > rover_x else -ROVER_STEP
        rover_moved = True
    if abs(drone_y - rover_y) > DRONE_THRESHOLD:
        rover_y += ROVER_STEP if drone_y > rover_y else -ROVER_STEP
        rover_moved = True
    if rover_moved:
        print(f"Rover moved -> X={rover_x:.2f}, Y={rover_y:.2f}")

    # Save rover path
    rover_path_x.append(rover_x)
    rover_path_y.append(rover_y)

    # Update plot
    drone_dot.set_data([drone_x], [drone_y])
    rover_dot.set_data([rover_x], [rover_y])
    drone_line.set_data(drone_path_x, drone_path_y)
    rover_line.set_data(rover_path_x, rover_path_y)

    return drone_dot, rover_dot, drone_line, rover_line

# --- Run Animation ---
ani = animation.FuncAnimation(fig, update, interval=100)
plt.show()
