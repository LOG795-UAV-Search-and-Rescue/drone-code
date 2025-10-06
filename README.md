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

### Production ready code

In order to use the full potential of `Go`, it's important to build the application using :

```shell
cd client
go build
```

This will create a file named `drone-code` in the `client/` directory.\
That file represents the built application that you can then run on any `VOXL2` drone.

To run the built code, run the following command in the directory where the build file is in your file system :

```shell
./drone-code    # on macOS/Linux
drone-code.exe  # on Windows
```

The backend communication client will then run on `192.168.8.1:9000` and the web interface on `192.168.8.1:8081` by default.\
These values can be changed by using the `--addr <your-address:and-port>` flag after the `go run` command or simply after the executable call.

> Made with care by [Adam Mihajlovic](https://github.com/Funnyadd), [Maxence Lord](https://github.com/ImprovUser) and [Raphaël Camara](https://github.com/RaphaelCamara) ❤️
