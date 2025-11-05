#!/usr/bin/env python3
import subprocess
import re
import time
import socket
import threading
import sys
import termios
import tty

# === CONFIG ===
PC_IP = "192.168.8.13"          # CHANGE before flight
UDP_PORT = 5005                 # UDP Port to send pose + commands

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Command: read qvio values
CMD = ["sudo", "voxl-inspect-qvio"]

pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

print(f"[VOXL] Streaming VIO data to {PC_IP}:{UDP_PORT}")
print("")
print("Controls:")
print("  F = Continuous Follow mode")
print("  C = Come-To-Me mode (rover waits)")
print("  SPACE/ENTER = Rover Come-To-Me NOW")
print("  Ctrl+C = Stop\n")

# === Key listener utilities ===
def getch():
    """Non-blocking single key reader"""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# === Key listener thread ===
def key_listener():
    while True:
        key = getch().lower()
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
    CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    universal_newlines=True, bufsize=1
)

try:
    for line in proc.stdout:
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
    print("\n[VOXL] Streaming stopped.")
finally:
    proc.terminate()
    sock.close()
