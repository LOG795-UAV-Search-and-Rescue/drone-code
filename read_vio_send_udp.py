#!/usr/bin/env python3
import subprocess
import re
import time
import socket

# === CONFIG ===
PC_IP = "192.168.8.13"     # Your PC IP
UDP_PORT = 5005            # UDP Port

# UDP socket setup
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Same command as before
CMD = ["sudo", "voxl-inspect-qvio"]

# Regex to extract X, Y, Z (pose)
pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
# Regex to extract quality percentage
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

print(f"[VOXL] Streaming VIO data via UDP to {PC_IP}:{UDP_PORT} (Ctrl+C to exit)")

proc = subprocess.Popen(
    CMD,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
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

            # Format packet as CSV-style plain text
            packet = f"{ts:.3f},{x:.3f},{y:.3f},{quality}"
            print(f"[LOCAL] {packet}")  # Still print locally for debug

            # Send via UDP
            sock.sendto(packet.encode(), (PC_IP, UDP_PORT))

except KeyboardInterrupt:
    print("\n[VOXL] Stopped streaming.")
finally:
    proc.terminate()
    sock.close()
