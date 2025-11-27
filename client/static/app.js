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
let worldOffsetX = 0;
let worldOffsetY = 0;


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
// MAP + ROVER + DRONE
// =====================================================
let mapCanvas, ctx;

let droneX = 0, droneY = 0, droneYaw = 0;
let roverX = 0, roverY = 0, roverO = 0;

const pixelsPerMeter = 150;

function worldToScreen(x, y) {
    x = x + worldOffsetX;
    y = y + worldOffsetY;
    return {
        x: mapCanvas.width / 2 + x * pixelsPerMeter,
        y: mapCanvas.height / 2 - y * pixelsPerMeter
    };
}

function screenToWorld(px, py) {
    return {
        x: (px - mapCanvas.width / 2) / pixelsPerMeter,
        y: (mapCanvas.height / 2 - py) / pixelsPerMeter
    };
}

function drawRoverTriangle(x, y, heading) {
    const pos = worldToScreen(x, y);
    const size = 15;

    ctx.save();
    ctx.translate(pos.x, pos.y);
    ctx.rotate(-heading);

    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size / 2, size);
    ctx.lineTo(-size / 2, size);
    ctx.closePath();

    ctx.fillStyle = "red";
    ctx.fill();

    ctx.restore();
}

function drawDroneTriangle(x, y, yawDeg) {
    const pos = worldToScreen(x, y);
    const size = 15;

    ctx.save();
    ctx.translate(pos.x, pos.y);

    const rad = yawDeg * Math.PI / 180;
    ctx.rotate(rad);

    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size / 2, size);
    ctx.lineTo(-size / 2, size);
    ctx.closePath();

    ctx.fillStyle = "cyan";
    ctx.fill();

    ctx.restore();
}

function drawMap() {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, mapCanvas.width, mapCanvas.height);

    drawDroneTriangle(droneX, droneY, droneYaw);
    drawRoverTriangle(roverX, roverY, roverO);
}

// =====================================================
// SEND ROVER COMMAND
// =====================================================
function sendCmd(cmd) {
    log("SEND → " + cmd);
    fetch("/api/rover-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cmd })
    });
}

// =====================================================
// CALIBRATION BUTTONS
// =====================================================
function sendCalib(path) {
    fetch(path, { method: "POST" })
        .then(r => r.text())
        .then(t => log("[CALIB] " + t))
        .catch(e => log("Calib error: " + e.message));
}

// =====================================================
// WEBSOCKET HANDLING
// =====================================================
function handlePacket(msg) {

    if (msg.startsWith("ROVER")) {
        const p = msg.split(",");
        roverX = parseFloat(p[1]);
        roverY = parseFloat(p[2]);
        roverO = parseFloat(p[3]);
        drawMap();
        return;
    }
    if (msg.startsWith("CALIB_DONE")) {
        log("[CALIB] Calibration complete. Recentering map.");

        // Recenter map so drone appears in middle
        worldOffsetX = -droneX;
        worldOffsetY = -droneY;

        drawMap();
        return;
    }


    if (msg.startsWith("CALIB_")) {
        log(msg);
        return;
    }
    

    const parts = msg.split(",");
    if (parts.length >= 4) {
        droneX = parseFloat(parts[1]);
        droneY = parseFloat(parts[2]);
        droneYaw = parseFloat(parts[3]);
        drawMap();
    }
}

// =====================================================
// INITIALIZATION
// =====================================================
window.addEventListener("DOMContentLoaded", () => {

    videoEl = $("video");

    $("connectBtn").addEventListener("click", () => {
        startWHEP().catch(err => {
            log(`Connect error: ${err.message}`);
            setStatus("error");
            scheduleReconnect();
        });
    });

    $("disconnectBtn").addEventListener("click", stopWHEP);
    $("recalibrateBtn").addEventListener("click", () => sendCalib("/api/recalibrate-yaw"));

    // 3-point calibration
    $("calibStart").addEventListener("click", () => sendCalib("/api/calib/start"));
    $("calibRight").addEventListener("click", () => sendCalib("/api/calib/right"));
    $("calibForward").addEventListener("click", () => sendCalib("/api/calib/forward"));
    $("calibFinish").addEventListener("click", () => sendCalib("/api/calib/finish"));

    // MAP
    mapCanvas = $("mapCanvas");
    ctx = mapCanvas.getContext("2d");

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

    // WebSocket
    let ws = new WebSocket("ws://" + window.location.hostname + ":8765");
    ws.onmessage = (ev) => handlePacket(ev.data);

    // periodic logs
    setInterval(() => {
        log(`[DRONE] x=${droneX.toFixed(2)}, y=${droneY.toFixed(2)}, yaw=${droneYaw.toFixed(1)}`);
        log(`[ROVER] x=${roverX.toFixed(2)}, y=${roverY.toFixed(2)}, o=${roverO.toFixed(2)}`);
    }, 5000);

    drawMap();
});
