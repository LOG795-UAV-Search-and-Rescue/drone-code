#!/usr/bin/env python3
import subprocess
import re
import time
import socket

# === CONFIG ===
PC_IP = "192.168.8.13"     # Your PC IP, WILL BE CHNAGED TO THE ROVER DW
UDP_PORT = 5005            # UDP Port


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# NEED SUDO TO ACCESS DATA IN QVIO PIPELINE
CMD = ["sudo", "voxl-inspect-qvio"]

# to extract x,y,z thats all
pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")

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

            
            packet = f"{ts:.3f},{x:.3f},{y:.3f},{quality}"
            print(f"[LOCAL] {packet}")  

       
            sock.sendto(packet.encode(), (PC_IP, UDP_PORT))

except KeyboardInterrupt:
    print("\n[VOXL] Stopped streaming.")
finally:
    proc.terminate()
    sock.close()
