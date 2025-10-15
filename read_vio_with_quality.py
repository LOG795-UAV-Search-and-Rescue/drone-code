#!/usr/bin/env python3
import subprocess
import re
import time

# Command to start qvio inspection NEED SUDO FOR PERMISSION
CMD = ["sudo", "voxl-inspect-qvio"]

# Eextract X, Y, Z (pose)
pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")

# Extract quality percentage (appears like '  |   85% |')
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

print("Starting voxl-inspect-qvio... (Ctrl+C to exit)")

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

        # Extract pose data
        pose_match = pose_regex.search(line)
        quality_match = quality_regex.search(line)

        if pose_match:
            x = float(pose_match.group(1))  # X
            y = float(pose_match.group(2))  # Y
            z = float(pose_match.group(3))  # Z (ignored for control)
            ts = time.time()

            # Extract quality if available, else show "-"
            quality = quality_match.group(1) + "%" if quality_match else "-"

            print(f"{ts:.3f}  X={x:.3f}  Y={y:.3f}  quality={quality}")

except KeyboardInterrupt:
    print("\nStopping reader...")
finally:
    proc.terminate()
