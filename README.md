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




Before running the Go program, make sure the following steps are done on the VOXL:

1. Configure cameras
sudo voxl-configure-cameras
sudo reboot

2. Camera server running

After reboot, check:
voxl-inspect-services | grep camera
You should see:
voxl-camera-server | Enabled | Running


3. QVIO server running
voxl-inspect-services | grep qvio

Should show:
voxl-qvio-server | Enabled | Running


Verify pose stream:
sudo voxl-inspect-qvio

Expected output (state OKAY, quality > 0, features > 0):
dt(ms) | T_imu_wrt_vio (m) | Roll Pitch Yaw (deg) | features | quality | state | error_codes

4. Vision hub running
voxl-inspect-services | grep vision
Should see:
voxl-vision-hub | Enabled | Running

5. MAVLink bridge enabled

Ensure voxl-vision-px4 is enabled (this publishes odometry over UDP):
voxl-inspect-services | grep px4
If not running:
sudo systemctl enable voxl-vision-px4
sudo systemctl start voxl-vision-px4

By default it publishes to udp://0.0.0.0:14550.

Then you should be ready to send a go file into the drone using the command:

scp *name of the file* voxl@192.168.8.1:/PFE/code/


NEW STEPS CHECK THAT QVIO IS RUNNING

# check VOXL modal services
voxl-inspect-services

# check qVIO service specifically
systemctl status voxl-qvio-server

# an easy inspect tool to show qVIO output
voxl-inspect-qvio

SHOULD SEE SOMETHING LIKE THIS WITH QUALITY COLUMN :
T_imu_wrt_vio (m)   |Roll Pitch Yaw (deg)| state| error_code
 -4.96    0.94   -0.00|  17.9  -52.3    9.3| OKAY |

## POUR LANCER LE SCRIPT (sur le drone)

cd ..
cd ..
cd PFE/code
METTRE LA BONNE ADRESSE IP DANS LE CODE
sudo nano read_vio_send_udp.py
Apres avoir changer ladresse ip lancer le script
python3 read_vio_send_udp.py

##Pour lancer le script (sur le PC)
python rover_follow_sim.py

**CAREFUL IF QUALITY IS TOO LOW POSITION RESETS SO X,Y,Z GOES BACK TO 0

## WELL HAVE TO ADD A LOGIC WHEN THE POSITIONNING RESETS TO 0 WHEN QUALITY IS VERY LOW, THEN MAYBE TELL TO THE ROVER THAT ITS THE NEW 0,0 Position in X,Y

