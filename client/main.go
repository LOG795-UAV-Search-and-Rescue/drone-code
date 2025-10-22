package main

import (
	"embed"
	"flag"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const (
	uiListenAddr   = ":8080"                 // UI HTTP listen address
	mediaMTXOrigin = "http://127.0.0.1:8889" // MediaMTX origin on the DRONE
)

//go:embed static/*
var staticFS embed.FS

func startUIServer() *http.Server {
	mux := http.NewServeMux()

	// Serve /static/ files on path "/"
	mux.Handle("/", http.FileServer(http.FS(staticFS)))

	// Serve api endpoints on path "/api"
	mux.HandleFunc("/api/call-ugv", func(w http.ResponseWriter, r *http.Request) {
		log.Printf("[UI] Call UGV pressed at %s from %s", time.Now().Format(time.RFC3339), r.RemoteAddr)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true,"message":"UGV call requested (logged on server)"}`))
	})

	// Proxy WHEP to MediaMTX
	u, err := url.Parse(mediaMTXOrigin)
	if err != nil {
		log.Fatalf("invalid mediaMTXOrigin: %v", err)
	}
	proxy := httputil.NewSingleHostReverseProxy(u)

	// Make sure to catch the right endpoint for the whep stream even with different url formats
	mux.Handle("/whep/", proxy)
	mux.Handle("/drone/whep", proxy)
	mux.Handle("/drone/whep/", proxy)

	srv := &http.Server{
		Addr:    uiListenAddr,
		Handler: mux,
	}

	go func() {
		log.Printf("UI listening on %s", uiListenAddr)
		log.Printf("Proxying /whep/* and /drone/whep* -> %s", mediaMTXOrigin)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("ui server error: %v", err)
		}
	}()

	return srv
}

// TCP Client (To communicate with the UGV robot)
func main() {
	addr := flag.String("addr", ":9000", "server address (host:port)")
	flag.Parse()
	// Add better log prefix
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	// Graceful shutdown when force closing the program
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	// Start the UI server
	uiServer := startUIServer()

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
			// Close UI server listener
			_ = uiServer.Close()
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

	// If stdin hits EOF, close write so the server sees it and then wait a moment.
	type closeWriter interface{ CloseWrite() error }
	if cw, ok := c.(closeWriter); ok {
		_ = cw.CloseWrite()
	}

	select {
	case <-done:
	case <-time.After(500 * time.Millisecond):
	}
}
