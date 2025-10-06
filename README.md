# drone-code
# VOXL MAVLink Odometry Export

This guide explains how to export Visual-Inertial Odometry (VIO) data from a ModalAI VOXL using the `voxl-mavlink-server` and receive it on a laptop via MAVLink/UDP.  
The data can then be logged in Python or bridged into ROS for visualization and navigation.

---

## System Overview

- **VOXL2** runs QVIO / OpenVINS → produces odometry.  
- **voxl-mavlink-server** exports MAVLink messages over UDP.  
- **Laptop (Python)** listens on UDP:14550 for MAVLink packets.  
- Data can be logged, plotted, or used in ROS2/MAVROS.

---

## 1. Configure VOXL

After connecting to the drone via ssh of course ;)

Edit the MAVLink server configuration:

```bash
sudo nano /etc/modalai/voxl-mavlink-server.conf
You will see these configs right now we are using the broadcast adress, but we could simply use the specific IP to then export the localization data of the drone at the out_udp_ip
{
    "out_udp_ip": "192.168.8.255",
    "out_udp_port": 14550,
    "out_udp_enabled": true,

    "send_odometry": true,
    "send_vision_estimate": true,
    "send_local_position": true
}

## 2. Restart service

sudo systemctl restart voxl-mavlink-server

## 3. Verify that its running

journalctl -u voxl-mavlink-server -f

sudo voxl-inspect-qvio

The data should be displayed like this and values will change as the drone moves :

dt(ms) |  T_imu_wrt_vio (m)   | Roll Pitch Yaw (deg) | features | quality | state
32.1   | -0.02 -0.09 -0.12    | 22.9  -5.8  -10.9    | 24       | 100%    | OKAY

## 4. For coding

pip install pymavlink

here is a basic listener code to display the localization data :

from pymavlink import mavutil

master = mavutil.mavlink_connection('udp:0.0.0.0:14550')
print("Listening for MAVLink...")

while True:
    msg = master.recv_match(blocking=True)
    if msg:
        print(msg.get_type(), msg.to_dict())





