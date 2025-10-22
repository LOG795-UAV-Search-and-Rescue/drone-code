# Drone Code

Code running on the Starling 2 Max with VOXL 2 drone.

## Getting started

### Requirements

In order to run the code in this repository, you'll need the following dependencies :

- **Go** (also known as GoLang) - version 1.25.1 is recommended

### Local development

To run the code in your local environment, you can use :

```shell
cd client # No need if you are already in the client/ folder
go run main.go
```

### Production-ready code

In order to use the full potential of `Go`, it's important to build the application by following the instructions below carefully.

> [!IMPORTANT]
> Make sure that you are in the `client/` folder when following the steps below.
> ```shell
> cd client # If you are at the root of the project
> ```

1. First, from the `client/` folder, tidy and update the `vendor/` folder :

    ```shell
    go mod tidy
    go mod vendor
    ```

2. Create an offline bundle (source + vendor), excluding junk :

    ```shell
    rm -rf drone-code-offline.tar.gz
    tar --exclude='.git' \
        --exclude='bin' \
        --exclude='.idea' \
        --exclude='.vscode' \
        --exclude='.DS_Store' \
        -czf drone-code-offline.tar.gz .
    ```

> [!WARNING]
> For the following steps, make sure that you are on the `VOXL-476723235` Wi-Fi when running the command below (password for that Wi-Fi is : `1234567890`).
>
> Also, the password for the user `voxl` connecting to the drone via **SCP/SSH** is : `voxl`.

3. Copy the offline-ready files to the drone :

    ```shell
    scp drone-code-offline.tar.gz voxl@192.168.8.1:/PFE/code
    ```

4. Build the project on the drone :

    In order to build the production-read code on the drone, you'll first want to SSH into it like this :
    ```shell
    ssh voxl@192.168.8.1
    ```

    Once you are inside the drone's terminal, you'll want to go to the folder where the code was uploaded and unzip the `tar.gz` :
    ```shell
    cd /PFE/code
    mkdir -p client
    tar -xzf drone-code-offline.tar.gz -C client --overwrite
    ```

    Then finally, go in the output folder and build the project like this :
    ```shell
    cd client
    go build
    ```

This will create a file named `drone-code` in the same directory.\
That file represents the built application that you can then run on any `VOXL2` drone.

To run the built code, run the following command in the directory where the build file is in your file system :

```shell
./drone-code
```

The backend communication client will then run on `192.168.8.1:9000` and the web interface on `192.168.8.1:8081` by default.\
These values can be changed by using the `--addr <your-address:and-port>` flag after the `go run` command or simply after the executable call.

> Made with care by [Adam Mihajlovic](https://github.com/Funnyadd), [Maxence Lord](https://github.com/ImprovUser) and [Raphaël Camara](https://github.com/RaphaelCamara) ❤️
