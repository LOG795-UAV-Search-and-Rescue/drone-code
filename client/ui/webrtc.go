package ui

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v3"

	"github.com/bluenviron/gortsplib/v4"
	"github.com/bluenviron/gortsplib/v4/pkg/base"
	"github.com/bluenviron/gortsplib/v4/pkg/description"
	"github.com/bluenviron/gortsplib/v4/pkg/format"
)

// SDP handler (browser offer -> server answer)

func handleOffer(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost || r.Header.Get("Content-Type") != "application/sdp" {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	offerBytes, _ := io.ReadAll(r.Body)
	offer := webrtc.SessionDescription{Type: webrtc.SDPTypeOffer, SDP: string(offerBytes)}

	// Media engine: register H264 and force PT=96 so it matches incoming RTSP (usually 96).
	m := webrtc.MediaEngine{}
	if err := m.RegisterCodec(webrtc.RTPCodecParameters{
		RTPCodecCapability: webrtc.RTPCodecCapability{
			MimeType:     webrtc.MimeTypeH264,
			ClockRate:    90000,
			SDPFmtpLine:  "level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f",
			RTCPFeedback: []webrtc.RTCPFeedback{{Type: "nack"}, {Type: "goog-remb"}, {Type: "ccm", Parameter: "fir"}},
		},
		PayloadType: webrtc.PayloadType(96),
	},
		webrtc.RTPCodecTypeVideo); err != nil {
		http.Error(w, "codec reg failed", http.StatusInternalServerError)
		return
	}

	api := webrtc.NewAPI(webrtc.WithMediaEngine(&m))
	pc, err := api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		http.Error(w, "pc create failed", http.StatusInternalServerError)
		return
	}

	// Single RTP track (H264)
	videoTrack, err := webrtc.NewTrackLocalStaticRTP(
		webrtc.RTPCodecCapability{MimeType: webrtc.MimeTypeH264, ClockRate: 90000},
		"video", "rtsp-h264",
	)
	if err != nil {
		_ = pc.Close()
		http.Error(w, "track failed", http.StatusInternalServerError)
		return
	}
	if _, err = pc.AddTrack(videoTrack); err != nil {
		_ = pc.Close()
		http.Error(w, "add track failed", http.StatusInternalServerError)
		return
	}

	// Ensure RTSP reader is running (lazy-start, once)
	rtspOnce.Do(func() {
		ctx, cancel := context.WithCancel(context.Background())
    	rtspCancel = cancel  
		go runRTSPReader(ctx, cfg.RTSPInput)
	})

	// Subscribe this Peer to incoming RTP packets
	rtpCh := make(chan *rtp.Packet, 512)
	registerRTPChan(rtpCh)
	go func() {
		defer unregisterRTPChan(rtpCh)
		var tsBase uint32
		var baseSet bool
		for pkt := range rtpCh {
			// Normalize timestamp base per-subscriber to avoid huge TS jumps
			p := *pkt
			if !baseSet {
				tsBase = p.Timestamp
				baseSet = true
			}
			p.Timestamp -= tsBase
			p.PayloadType = 96 // Match registered codec
			if err := videoTrack.WriteRTP(&p); err != nil {
				return
			}
		}
	}()

	// SDP handshake
	if err = pc.SetRemoteDescription(offer); err != nil {
		_ = pc.Close()
		http.Error(w, "set remote failed", http.StatusInternalServerError)
		return
	}
	answer, err := pc.CreateAnswer(nil)
	if err != nil {
		_ = pc.Close()
		http.Error(w, "answer failed", http.StatusInternalServerError)
		return
	}
	gather := webrtc.GatheringCompletePromise(pc)
	if err = pc.SetLocalDescription(answer); err != nil {
		_ = pc.Close()
		http.Error(w, "set local failed", http.StatusInternalServerError)
		return
	}
	<-gather

	w.Header().Set("Content-Type", "application/sdp")
	_, _ = io.Copy(w, bytes.NewReader([]byte(pc.LocalDescription().SDP)))

	pc.OnConnectionStateChange(func(s webrtc.PeerConnectionState) {
		log.Printf("[webrtc] state: %s", s)
		if s == webrtc.PeerConnectionStateFailed ||
			s == webrtc.PeerConnectionStateClosed ||
			s == webrtc.PeerConnectionStateDisconnected {
			_ = pc.Close()
		}
	})
}

// RTSP reader
var (
	rtspOnce   sync.Once
	rtspMu     sync.RWMutex
	rtspSubs   = make([]chan *rtp.Packet, 0)
	rtspCancel context.CancelFunc
)

func registerRTPChan(ch chan *rtp.Packet) {
	rtspMu.Lock()
	defer rtspMu.Unlock()
	rtspSubs = append(rtspSubs, ch)
}

func unregisterRTPChan(ch chan *rtp.Packet) {
	rtspMu.Lock()
	defer rtspMu.Unlock()
	for i, c := range rtspSubs {
		if c == ch {
			close(c)
			rtspSubs = append(rtspSubs[:i], rtspSubs[i+1:]...)
			break
		}
	}
}

func fanout(pkt *rtp.Packet) {
	rtspMu.RLock()
	defer rtspMu.RUnlock()
	for _, ch := range rtspSubs {
		select {
		case ch <- pkt:
		default: /* drop if slow */
		}
	}
}

func runRTSPReader(ctx context.Context, rtspURL string) {
	for {
		if err := runRTSPOnce(ctx, rtspURL); err != nil {
			log.Printf("[rtsp] error: %v (reconnect in 2s)", err)
			select {
			case <-ctx.Done():
				return
			case <-time.After(2 * time.Second):
			}
			continue
		}
		return
	}
}

func runRTSPOnce(ctx context.Context, rtspURL string) error {
	u, err := base.ParseURL(rtspURL)
	if err != nil {
		return fmt.Errorf("parse url: %w", err)
	}

	var c gortsplib.Client
	if err := c.Start2(); err != nil { // init client state machine
		return fmt.Errorf("start: %w", err)
	}
	defer c.Close()

	if _, err = c.Options(u); err != nil {
		return fmt.Errorf("options: %w", err)
	}

	desc, _, err := c.Describe(u)
	if err != nil {
		return fmt.Errorf("describe: %w", err)
	}

	// Find H264 media/format
	var medi *description.Media
	var h264f *format.H264
outer:
	for _, m := range desc.Medias {
		for _, f := range m.Formats {
			if hf, ok := f.(*format.H264); ok {
				medi = m
				h264f = hf
				break outer
			}
		}
	}

	if medi == nil || h264f == nil {
		return fmt.Errorf("no H264 in remote description")
	}

	// Receive RTP for this media
	c.OnPacketRTP(medi, h264f, func(pkt *rtp.Packet) {
		fanout(pkt)
	})

	// Setup & Play
	if _, err = c.Setup(u, medi, 0, 0); err != nil {
		return fmt.Errorf("setup: %w", err)
	}

	if _, err = c.Play(nil); err != nil {
		return fmt.Errorf("play: %w", err)
	}

	// Stop when context is done
	done := make(chan struct{})
	go func() {
		<-ctx.Done()
		c.Close()
		close(done)
	}()

	err = c.Wait()
	<-done
	return err
}

// StopWebUI stops the RTSP reader and closes subscriber channels.
func StopWebUI() {
    rtspMu.Lock()
    if rtspCancel != nil {
        rtspCancel()
        rtspCancel = nil
    }
    // close all subscriber chans to unblock writers
    for _, ch := range rtspSubs {
        close(ch)
    }
    rtspSubs = nil
    rtspMu.Unlock()
}
