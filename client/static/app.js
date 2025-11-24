// =====================================================
// GLOBAL HELPERS
// =====================================================
const $ = (id) => document.getElementById(id);

function log(msg) {
    const el = $("log");
    const ts = new Date().toISOString().split("T")[1].replace("Z", "");
    el.textContent += `[${ts}] ${msg}\n`;
    el.scrollTop = el.scrollHeight;
}

// =====================================================
// VIDEO STREAM (WHEP)
// =====================================================
const WHEP_URL = "/drone/whep";
let pc = null;
let videoEl = null;
let reconnectTimer = null;
let closing = false;

const RETRY_BASE_MS = 500;
const RETRY_MAX_MS = 5000;

function setStatus(s) { $("status").textContent = s; }
function setBtns({ connected }) {
    $("connectBtn").disabled = connected;
    $("disconnectBtn").disabled = !connected;
}

async function startWHEP() {
    closing = false;
    clearTimeout(reconnectTimer);
    if (pc) await stopWHEP();

    setStatus("connecting...");
    setBtns({ connected: false });

    pc = new RTCPeerConnection({ iceServers: [] });
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.ontrack = (e) => {
        if (!videoEl.srcObject) videoEl.srcObject = e.streams[0];
    };

    pc.onconnectionstatechange = () => {
        log(`PeerConnection: ${pc.connectionState}`);
        if (pc.connectionState === "connected") {
            setStatus("connected");
            setBtns({ connected: true });
        } else if (["failed", "disconnected"].includes(pc.connectionState)) {
            setStatus(pc.connectionState);
            setBtns({ connected: false });
            if (!closing) scheduleReconnect();
        }
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    await new Promise((resolve) => {
        if (pc.iceGatheringState === "complete") return resolve();
        pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === "complete") resolve();
        };
    });

    const resp = await fetch(WHEP_URL, {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: pc.localDescription.sdp,
    });

    if (!resp.ok) throw new Error(`WHEP HTTP ${resp.status}`);
    const answerSDP = await resp.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSDP });

    log("WHEP session established");
    setStatus("connected");
    setBtns({ connected: true });
}

async function stopWHEP() {
    closing = true;
    clearTimeout(reconnectTimer);
    setStatus("disconnecting...");

    try {
        if (pc) {
            pc.ontrack = null;
            pc.onconnectionstatechange = null;
            pc.getSenders().forEach(s => s.track && s.track.stop());
            pc.getReceivers().forEach(r => r.track && r.track.stop());
            pc.close();
        }
    } catch {}

    pc = null;
    if (videoEl && videoEl.srcObject) {
        try {
            videoEl.srcObject.getTracks().forEach(t => t.stop());
        } catch {}
        videoEl.srcObject = null;
    }

    setBtns({ connected: false });
    setStatus("idle");
    log("WHEP session closed");
}

function scheduleReconnect() {
    let delay = reconnectTimer ? Math.min(RETRY_MAX_MS, RETRY_BASE_MS * 2) : RETRY_BASE_MS;
    reconnectTimer = setTimeout(() => {
        log("Reconnecting...");
        startWHEP().catch(err => {
            log(`Reconnect failed: ${err.message}`);
            scheduleReconnect();
        });
    }, delay);
}

// =====================================================
// MAP + ROVER CLICK-GOTO
// =====================================================
let mapCanvas, ctx;
let droneX = 0, droneY = 0;
const pixelsPerMeter = 20;

function updateMap(packet) {
    const parts = packet.split(",");
    if (parts.length < 4) return;

    droneX = parseFloat(parts[1]);
    droneY = parseFloat(parts[2]);
    drawMap();
}

function drawMap() {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, mapCanvas.width, mapCanvas.height);

    const sx = mapCanvas.width / 2 + droneX * pixelsPerMeter;
    const sy = mapCanvas.height / 2 - droneY * pixelsPerMeter;

    ctx.fillStyle = "cyan";
    ctx.beginPath();
    ctx.arc(sx, sy, 6, 0, Math.PI * 2);
    ctx.fill();
}

function screenToWorld(px, py) {
    return {
        x: (px - mapCanvas.width / 2) / pixelsPerMeter,
        y: (mapCanvas.height / 2 - py) / pixelsPerMeter
    };
}

// Send rover command
function sendCmd(cmd) {
    log("SEND → " + cmd);
    fetch("/api/rover-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cmd })
    });
}

// =====================================================
// INITIALIZATION
// =====================================================
window.addEventListener("DOMContentLoaded", () => {
    // Video
    videoEl = $("video");

    $("connectBtn").addEventListener("click", () => {
        startWHEP().catch(err => {
            log(`Connect error: ${err.message}`);
            setStatus("error");
            scheduleReconnect();
        });
    });

    $("disconnectBtn").addEventListener("click", stopWHEP);

    $("callUgvBtn").addEventListener("click", async () => {
        log("Call UGV pressed");
        try {
            const r = await fetch("/api/call-ugv", { method: "POST" });
            const j = await r.json();
            log(`Server: ${j.message}`);
        } catch (e) {
            log(`Server error: ${e.message}`);
        }
    });

    // AUTO CONNECT VIDEO
    startWHEP().catch(err => {
        log(`Auto-connect error: ${err.message}`);
        scheduleReconnect();
    });

    // MAP
    mapCanvas = $("mapCanvas");
    ctx = mapCanvas.getContext("2d");

    // WebSocket for VIO
    let ws = new WebSocket("ws://" + window.location.hostname + ":8765");
    ws.onmessage = (ev) => {
        log("[VIO] " + ev.data);
        updateMap(ev.data);
    };

    // Left click → GOTO command
    mapCanvas.addEventListener("click", (e) => {
        const rect = mapCanvas.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const py = e.clientY - rect.top;

        const w = screenToWorld(px, py);
        const x = w.x.toFixed(2);
        const y = w.y.toFixed(2);

        log(`CLICK → GOTO ${x}, ${y}`);

        sendCmd(`GOTO ${x} ${y}`);
    });

    drawMap();
});
