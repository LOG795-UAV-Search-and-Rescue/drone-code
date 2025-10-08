package main

import (
	"context"
	"flag"
	"io"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ets-log795/drone-code/ui"
)

func main() {
	const DEFAULT_ROBOT_ADDRESS = "192.168.8.2:9000"
	const DEFAULT_WEB_UI_ADDRESS = "0.0.0.0:8080"
	const DEFAULT_RTSP_ADDRESS = "rtsp://127.0.0.1:8900/live"

	// Ability to set address and port from command args (go main.go --addr=<address>)
	serverAddr := flag.String("addr", DEFAULT_ROBOT_ADDRESS, "server address (host:port)")
	uiAddr := flag.String("ui", DEFAULT_WEB_UI_ADDRESS, "web UI address (host:port)")
	rtspAddr := flag.String("rtsp", DEFAULT_RTSP_ADDRESS, "RTSP address for WebRTC (host:port)")
	flag.Parse()

	// Add better log prefix
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	// Graceful shutdown when force closing the program
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Start the Web UI (runs independently of the TCP client)
	go ui.StartWebUI(*uiAddr, *rtspAddr)

	// Initiate connection to the server (UGV robot)
	dial := func() (net.Conn, error) {
		dialer := &net.Dialer{Timeout: 5 * time.Second, KeepAlive: 30 * time.Second}
		return dialer.Dial("tcp", *serverAddr)
	}

	// Reconnection loop
	for {
		select {
		case <-ctx.Done():
			log.Println("exiting")
			ui.StopWebUI()
			return
		default:
		}

		var conn, err = dial()
		if err != nil {
			log.Printf("connection failed: %v (retrying in 2s)", err)
			select {
			case <-ctx.Done():
				return
			case <-time.After((2 * time.Second)):
				continue
			}
		}

		log.Printf("connected to %s", *serverAddr)
		run(ctx, conn)

		select {
		case <-ctx.Done():
			return
		case <-time.After(2 * time.Second):
			log.Println("disconnected; reconnecting ...")
		}
	}
}

func run(ctx context.Context, c net.Conn) {
	defer c.Close()

	// Reader: socket -> stdout
	readDone := make(chan error, 1)
	go func() {
		_, err := io.Copy(os.Stdout, c)
		readDone <- err
	}()

	// Writer: stdin -> socket
	writeDone := make(chan error, 1)
	go func() {
		_, err := io.Copy(c, os.Stdin)
		writeDone <- err
	}()

	// Wait for any type of shutdown or read/write to finish
	select {
	case <-ctx.Done():
		_ = c.SetDeadline(time.Now())
		_ = c.Close()
	case <-readDone:
	case <-writeDone:
		type closeWriter interface{ closeWrite() error }

		if cw, ok := c.(closeWriter); ok {
			_ = cw.closeWrite()
		}
	}

	// Give the other goroutine a moment to exit cleanly
	select {
	case <-readDone:
	case <-writeDone:
	case <-time.After(300 * time.Millisecond):
	}
}
