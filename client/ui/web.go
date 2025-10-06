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

func StartWebUI(port string) {
	mux := http.NewServeMux()
	mux.HandleFunc("/", serveUI)
	mux.HandleFunc("/send-point", handleSendPoint)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	log.Printf("Web UI available at http://0.0.0.0%s (try http://192.168.8.1%s)", port, port)
	if err := http.ListenAndServe(port, mux); err != nil {
		log.Printf("web ui error: %v", err)
	}
}

func serveUI(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, htmlUI)
}

func handleSendPoint(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	defer r.Body.Close()

	var p ClickPoint
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	// Right now it logs to the console but will need to send info to robot enventually
	log.Printf("[UI] Clicked at X=%.2f%% Y=%.2f%%", p.XPercent, p.YPercent)

	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}
