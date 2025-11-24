const WHEP_URL = "/drone/whep";

const RETRY_BASE_MS = 500;
const RETRY_MAX_MS  = 5000;

let pc = null;
let videoEl = null;
let reconnectTimer = null;
let closing = false;

const $ = (id) => document.getElementById(id);
const log = (m) => {
    const el = $("log");
    const ts = new Date().toISOString().split("T")[1].replace("Z","");
    el.textContent += `[${ts}] ${m}\n`;
    el.scrollTop = el.scrollHeight;
};
const setStatus = (s) => $("status").textContent = s;
const setBtns = ({ connected }) => {
    $("connectBtn").disabled = connected;
    $("disconnectBtn").disabled = !connected;
};

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
        } else if (["failed","disconnected"].includes(pc.connectionState)) {
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
    }
    catch {}

    pc = null;
    if (videoEl && videoEl.srcObject) {
        try {
            videoEl.srcObject.getTracks().forEach(t => t.stop());
        }
        catch {}

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

window.addEventListener("DOMContentLoaded", () => {
    videoEl = $("video");

    $("connectBtn").addEventListener("click", () => {
        startWHEP().catch(err => {
            log(`Connect error: ${err.message}`);
            setStatus("error");
            scheduleReconnect();
        });
    });

    $("disconnectBtn").addEventListener("click", () => stopWHEP());

    $("callUgvBtn").addEventListener("click", async () => {
        log("Call UGV pressed");
        try {
            const r = await fetch("/api/call-ugv", { method: "POST" });
            const j = await r.json().catch(() => ({}));
            log(`Server: ${j.message || "ok"}`);
        } catch (e) {
            log(`Server error: ${e.message}`);
        }
    });

    // Auto-connect on load
    startWHEP().catch(err => {
        log(`Auto-connect error: ${err.message}`);
        scheduleReconnect();
    });
});

// =====================================================
// MAP + WEBSOCKET + RIGHT-CLICK ROVER COMMANDS
// =====================================================

// Connect to the drone WebSocket for VIO packets
let vioSocket = new WebSocket("ws://" + window.location.hostname + ":8765");

vioSocket.onmessage = (ev) => {
    let msg = ev.data.trim();
    log("[VIO] " + msg);
    updateMapPosition(msg);
};

// --- MAP SETUP ---
const canvas = document.getElementById("mapCanvas");
const ctx = canvas.getContext("2d");


const pixelsPerMeter = 50; //MAP BIG OR SMALL HERE


let droneX = 0;
let droneY = 0;

function updateMapPosition(packet) {
    let parts = packet.split(",");
    if (parts.length < 4) return;

    let x = parseFloat(parts[1]);
    let y = parseFloat(parts[2]);
    droneX = x;
    droneY = y;
    drawMap();
}

function worldToScreen(x, y) {
    let cx = canvas.width / 2;
    let cy = canvas.height / 2;
    return {
        x: cx + x * pixelsPerMeter,
        y: cy - y * pixelsPerMeter
    };
}

function screenToWorld(px, py) {
    let cx = canvas.width / 2;
    let cy = canvas.height / 2;
    return {
        x: (px - cx) / pixelsPerMeter,
        y: (cy - py) / pixelsPerMeter
    };
}

function drawMap() {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    let pos = worldToScreen(droneX, droneY);
    ctx.fillStyle = "cyan";
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 6, 0, Math.PI * 2);
    ctx.fill();
}

// --- RIGHT CLICK HANDLER ---
canvas.addEventListener("click", function (e) {

    let rect = canvas.getBoundingClientRect();
    let px = e.clientX - rect.left;
    let py = e.clientY - rect.top;

    let world = screenToWorld(px, py);
    let x = world.x.toFixed(2);
    let y = world.y.toFixed(2);

    log(`CLICK → GOTO ${x}, ${y}`);

    fetch("/api/rover-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cmd: `GOTO ${x} ${y}` })
    })
    .then(r => r.text())
    .then(t => log("[ROVER] " + t))
    .catch(err => log("[ROVER ERROR] " + err));
});


