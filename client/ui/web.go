package ui

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

// ClickPoint represents a normalized click position (0 - 100%)
type ClickPoint struct {
	XPercent float64 `json:"xPercent"`
	YPercent float64 `json:"yPercent"`
}

type Config struct {
	UIAddr    string
	RTSPInput string
}

var cfg Config

func StartWebUI(addr, rtspURL string) {
	cfg = Config{UIAddr: addr, RTSPInput: rtspURL}

	mux := http.NewServeMux()
	mux.HandleFunc("/", serveUI)
	mux.HandleFunc("/send-point", handleSendPoint)
	mux.HandleFunc("/offer", handleOffer)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	log.Printf("[ui] Web UI available at %s | RTSP source: %s", cfg.UIAddr, cfg.RTSPInput)
	if err := http.ListenAndServe(cfg.UIAddr, mux); err != nil {
		log.Printf("[ui] web ui error: %v", err)
	}
}

func serveUI(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, htmlUI)
}

func handleSendPoint(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "[ui] method not allowed", http.StatusMethodNotAllowed)
		return
	}
	defer r.Body.Close()

	var p ClickPoint
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		http.Error(w, "[ui] bad request", http.StatusBadRequest)
		return
	}

	// Right now it logs to the console but will need to send info to robot enventually
	log.Printf("[ui] Clicked at X=%.2f%% Y=%.2f%%", p.XPercent, p.YPercent)

	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}
