#!/usr/bin/env python3
import subprocess
import re
import time
import socket
import threading
import sys
import termios
import tty
import getpass


running = True


PC_IP = "192.168.8.2"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("This script requires sudo privileges.")
sudo_password = getpass.getpass("Enter sudo password: ")

# === Test sudo password (Python 3.6 FIX) ===
test = subprocess.run(
    ["sudo", "-S", "echo", "OK"],
    input=sudo_password + "\n",
    universal_newlines=True,          
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

if "OK" not in test.stdout:
    print("Wrong sudo password. Exiting.")
    sys.exit(1)

print("Sudo authentication successful.\n")

# Command: read qvio values (non-interactive sudo)
CMD = ["sudo", "-S", "voxl-inspect-qvio"]

pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

print(f"[VOXL] Streaming VIO data to {PC_IP}:{UDP_PORT}")
print("Controls:")
print("  F = Continuous Follow mode")
print("  C = Come-To-Me mode (rover waits)")
print("  SPACE/ENTER = Rover Come-To-Me NOW")
print("  Q = Quit program")
print("  Ctrl+C = Emergency stop\n")

# === Key reader ===
def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# === Key listener thread ===
def key_listener():
    global running
    while running:
        key = getch().lower()

        if key == 'q':
            print("[KEYBOARD] Quit requested.")
            running = False
            break

        if key == 'f':
            sock.sendto(b"MODE_CONTINUOUS", (PC_IP, UDP_PORT))
            print("[KEYBOARD] ➜ Sent MODE_CONTINUOUS")
        elif key == 'c':
            sock.sendto(b"MODE_COME_TO_ME", (PC_IP, UDP_PORT))
            print("[KEYBOARD] ➜ Sent MODE_COME_TO_ME")
        elif key == ' ' or key == '\n':
            sock.sendto(b"CMD_COME_TO_ME", (PC_IP, UDP_PORT))
            print("[KEYBOARD] ➜ Sent CMD_COME_TO_ME")

threading.Thread(target=key_listener, daemon=True).start()

# === Start QVIO subprocess ===
proc = subprocess.Popen(
    CMD,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,        # <-- Python 3.6 compatible
    bufsize=1
)

# Send sudo password once
proc.stdin.write(sudo_password + "\n")
proc.stdin.flush()

# === Main loop ===
try:
    for line in proc.stdout:
        if not running:
            break

        if not line:
            continue

        line = line.strip()
        pose_match = pose_regex.search(line)
        quality_match = quality_regex.search(line)

        if pose_match:
            x = float(pose_match.group(1))
            y = float(pose_match.group(2))
            ts = time.time()
            quality = quality_match.group(1) if quality_match else "-"

            packet = f"{ts:.3f},{x:.3f},{y:.3f},{quality}"
            sock.sendto(packet.encode(), (PC_IP, UDP_PORT))

except KeyboardInterrupt:
    print("\nEmergency stop (Ctrl+C).")

finally:
    running = False
    proc.terminate()
    sock.close()
    print("Program closed cleanly.")
