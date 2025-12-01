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

## Web interface

The web interface can be accessed through http://192.168.8.1:8080.

### Camera issues

If you have issues with the camera preview in the web interface. You can try to restart the `mediaMTX` service by executing the command below in the drone's **CLI**.

```shell
sudo systemctl restart mediamtx
```

### Calibrating the drone's position in the interface
Place your drone on the origin point (it's whatever you decide the origin is)
1. Click on the `Save Point A` button.
2. Move the drone to the right (from the drone's perspective) and Click on the `Save Point B` button.
3. Move the Drone Back to Origin (**it's important to actually go back to the origin and not skip this step**).
4. Move the drone forward (again, from the drone's perspective) and click on the `Save Point C` button.
5. Bring the drone back to the origin.
6. Click on the `Finish Calibration` button to complete the calibration.

Now when you move the drone around, its mouvement will be accurately tracked and displayed on the map.


> Made with care by [Adam Mihajlovic](https://github.com/Funnyadd), [Maxence Lord](https://github.com/ImprovUser) and [Raphaël Camara](https://github.com/RaphaelCamara) ❤️
