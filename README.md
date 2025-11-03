# VOXL Drone → PC VIO Tracking + Rover Follow System

This project streams Visual-Inertial Odometry (VIO) from a **ModalAI VOXL** to a laptop over UDP, then uses that localization to simulate (and optionally command) a UGV rover that follows the drone.
 VOXL → Laptop VIO in real-time  
Laptop processes pose & controls rover  
GUI simulation showing drone + rover  
Handles signal drop, low quality, VOXL resets  
Option to control Waveshare UGV via JSON  
Manual IP entry in script

---

## System Overview

```
VOXL Cameras → QVIO → UDP → Laptop → Rover Commands
         |                                  |
     Quality & Reset Logic      Matplotlib Interface + UGV JSON
```

---

## Requirements

| Component | Version |
|---|---|
VOXL / VOXL2 | QVIO enabled |
Python | 3.10+ |
Packages | matplotlib, socket, json, math |

---

## VOXL Setup

### 1. SSH into VOXL

```bash
ssh voxl@192.168.8.1
```

### 2. Configure cameras

```bash
sudo voxl-configure-cameras
sudo reboot
```

### 3. Validate VOXL services

Camera server:

```bash
voxl-inspect-services | grep camera
```

VIO system:

```bash
voxl-inspect-services | grep qvio
sudo voxl-inspect-qvio
```

✅ Expect moving pose, `OKAY`, quality > 0.

### 4. Copy VIO export script to VOXL

```bash
scp read_vio_send_udp.py voxl@192.168.8.1:/PFE/code/
```

Edit PC IP inside script:

```bash
nano read_vio_send_udp.py
```

Update:

```python
PC_IP = "YOUR_PC_IP"
```

### 5. Run VIO stream

```bash
cd /PFE/code
sudo python3 read_vio_send_udp.py
```

---

## Laptop Setup

Install Python deps:

```bash
pip install matplotlib
```

Run simulation:

```bash
python3 rover_follow_sim.py
```

---

## Data Format

Drone sends:

```
timestamp, x, y, quality, reset_flag
```

Example:

```
1758737264.788,-0.01,0.09,66,0
```

---

## Rover Behavior

Mode | Action
---|---
Normal follow | Rover follows drone smoothly
Low VIO quality | Ignore bad data & hold last pose
Reset | Rover goes to last known drone pose, then resets to 0,0

---

## GUI Status Colors

| Color | Meaning |
|---|---|
🔵 Blue | Drone valid position  
⚪ Gray | Low VIO quality  
🔴 Red | Rover following  
🟡 Yellow | Reset-sync in progress  

---

## Real Rover (optional)

This system sends JSON:

```json
{"T": 0.42, "L": 0.31, "R": 0.53}
```

Change in script to your rover IP/port.

---

## Troubleshooting

| Problem | Fix |
|---|---|
Drone stuck at 0 | Sensors blocked / bad texture |
No UDP | Wrong IP/network |
Erratic jumps | Low features — handled by filter |

---

## Notes

- VOXL VIO resets indoors are normal
- Hand covering cameras drops features
- Manual IP config chosen for clarity

---

## Future Work

- Trigger follow mode
- Real UGV integration demo
- ROS2 bridge
