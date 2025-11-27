# Drone Code

Code running on the Starling 2 Max with VOXL 2 drone.

## Getting started

### Requirements (Local machine)

In order to run the code in this repository, you'll need the following dependencies :

- **Python 3.6.9+**
- Access to the drone's network (VOXL-xxxxxx, password: `1234567890`) 
- Drone SSH/SCP login:
  - **user**: `voxl`
  - **password**: `voxl`

### Running locally

From the `client/` folder:
```bash
python3 main.py
```

UI will be available at:
```shell
http://localhost:8080
```

WHEP proxy will forward to:
```shell
http://127.0.0.1:8889
```

### Preparing a Full Offline Package

Since the drone is **offline**, you must send **all source files** at once.

- Create the offline bundle
    
    From inside the `client/` folder:
    ```shell
    rm -f drone-ui-offline.tar.gz

    tar --exclude='.git' \
        --exclude='.idea' \
        --exclude='.vscode' \
        --exclude='.DS_Store' \
        --exclude='send_to_drone.sh' \
        -czf drone-ui-offline.tar.gz .
    ```

    This produces:
    ```shell
    drone-ui-offline.tar.gz
    ```

### Sending the Package to the drone

> [!IMPORTANT]
> You must be connected to the drone's Wi-Fi:\
> SSID/name: `VOXL-476723235`\
> Password: `1234567890`

Send the offline package:
```shell
scp drone-ui-offline.tar.gz voxl@192.168.8.1:/PFE/code
```

Enter password: `voxl`

### Installing & Running on the Drone

SSH into the drone:
```
ssh voxl@192.168.8.1
```

Extract the package:
```shell
cd /PFE/code
rm -rf client
mkdir client
tar -xzf drone-ui-offline.tar.gz -C client --overwrite
```

Run the Python server:
```shell
cd client
python3 main.py
```

The UI will be accessible from your computer on:
```shell
http://192.168.8.1:8080
```

The UI uses `/drone/whep` which the Python server will proxy to MediaMTX running locally on VOXL2:
```shell
http://127.0.0.1:8889/whep
```

### IF ISSUES WITH CAMERA

sudo systemctl restart mediamtx
# TO CALIBRATE
##  Place your drone on the origin point (its what ever you decide the origin is)
  - Hit Save Point A
  - Then Move the drone to the right and Hit Save Point B
  - Move the Drone Back to Origin
  - Then move the drone forward and Hit Save Point C
  - Bring the drone back to the origin
  - Then Finish Calibration
### The Map will reset 
Now when you mvoe the drone forward and to the sides the map will accuretly display it.


> Made with care by [Adam Mihajlovic](https://github.com/Funnyadd), [Maxence Lord](https://github.com/ImprovUser) and [Raphaël Camara](https://github.com/RaphaelCamara) ❤️
