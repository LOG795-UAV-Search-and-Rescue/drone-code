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

# === GLOBAL STATE ===
running = True   # to close connection

# === CONFIG ===
PC_IP = "192.168.8.13"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("This script requires sudo privileges.")
sudo_password = getpass.getpass("Enter sudo password: ")

# Test sudo password
test = subprocess.run(
    ["sudo", "-S", "echo", "OK"],
    input=sudo_password + "\n",
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

if "OK" not in test.stdout:
    print("Wrong sudo password. Exiting.")
    sys.exit(1)

print("Sudo authentication successful.\n")

CMD = ["sudo", "-S", "voxl-inspect-qvio"]

pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

print("Controls:")
print("  F = Continuous Follow mode")
print("  C = Come-To-Me mode")
print("  SPACE/ENTER = Rover Come-To-Me NOW")
print("  Q = Quit program")
print("")

# === Key listener utilities ===
def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# === KEY LISTENER THREAD ===
def key_listener():
    global running
    while running:
        key = getch().lower()

        if key == 'q':
            print("\n[KEYBOARD] Quit command received. Stopping...")
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

# === Stream VIO ===
proc = subprocess.Popen(
    CMD,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
)

proc.stdin.write(sudo_password + "\n")
proc.stdin.flush()

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

except Exception as e:
    print("Error:", e)

finally:
    print("\nShutting down...")
    running = False
    proc.terminate()
    sock.close()
    print("Program closed cleanly.")
