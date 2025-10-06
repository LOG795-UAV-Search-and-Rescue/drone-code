package main

import (
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
	// Ability to set address and port from command args (go main.go --addr=<address>)
	addr := flag.String("addr", ":9000", "server address (host:port)")
	uiPort := flag.String("ui", ":8081", "web UI port (host:port)")
	flag.Parse()

	// Add better log prefix
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	// Start the Web UI (runs independently of the TCP client)
	go ui.StartWebUI(*uiPort) // http://192.168.8.1:8081 by default

	// Graceful shutdown when force closing the program
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	// Initiate connection to the server (UGV robot)
	var conn net.Conn
	var err error
	dial := func() (net.Conn, error) {
		dialer := &net.Dialer{Timeout: 5 * time.Second, KeepAlive: 30 * time.Second}
		return dialer.Dial("tcp", *addr)
	}

	// Reconnection loop
	for {
		select {
		case <-sig:
			log.Println("exiting")
			return
		default:
		}

		conn, err = dial()
		if err != nil {
			log.Printf("connection failed: %v (retrying in 2s)", err)
			time.Sleep(2 * time.Second)
			continue
		}
		log.Printf("connected to %s", *addr)
		run(conn)

		log.Println("disconnected; reconnecting in 2s ...")
		time.Sleep(2 * time.Second)
	}
}

func run(c net.Conn) {
	defer c.Close()

	// Pipe: socket -> stdout
	done := make(chan struct{}, 1)
	go func() {
		_, _ = io.Copy(os.Stdout, c)
		done <- struct{}{}
	}()

	// Pipe: stdin -> socket
	_, _ = io.Copy(c, os.Stdin)

	// If stdin hits EOF, close write so the server sees it; then wait a moment.
	type closeWriter interface{ CloseWrite() error }
	if cw, ok := c.(closeWriter); ok {
		_ = cw.CloseWrite()
	}

	select {
	case <-done:
	case <-time.After(500 * time.Millisecond):
	}
}
