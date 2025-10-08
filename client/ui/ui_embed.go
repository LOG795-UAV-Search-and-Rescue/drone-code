package ui

const htmlUI = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Drone Control UI (WebRTC)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      :root { color-scheme: dark; }
      body {
        background:#0f1115; color:#e8e8e8; margin:0; padding:16px;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        display:flex; flex-direction:column; align-items:center; gap:12px;
      }
      h2 { margin: 2px 0 8px; }
      #video-wrap { position:relative; width:min(95vw,1200px); aspect-ratio:16/9; border:1px solid #2a2f3a; border-radius:10px; overflow:hidden; background:#000; }
      #webrtc { width:100%; height:100%; background:#000; }
      #overlay { position:absolute; inset:0; cursor: crosshair; }
      #marker {
        position:absolute; width:12px; height:12px; background:#ff3b3b;
        border:2px solid #fff; border-radius:50%; transform:translate(-50%,-50%);
        pointer-events:none; display:none; box-shadow:0 0 10px rgba(255,59,59,.8);
      }
      #hud { position:absolute; left:10px; bottom:10px; background:rgba(15,17,21,.65); padding:6px 10px; border-radius:8px; font-size:12px; }
      #controls { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
      button { background:#1a73e8; color:white; border:none; padding:10px 16px; border-radius:8px; cursor:pointer; font-weight:600; }
      button:disabled { opacity:.55; cursor:not-allowed; }
      .muted { opacity:.7; font-size:12px; }
    </style>
  </head>
  <body>
    <h2>Drone Live Feed (WebRTC)</h2>

    <div id="video-wrap">
      <video id="webrtc" autoplay playsinline muted></video>
      <div id="overlay"></div>
      <div id="marker"></div>
      <div id="hud"><span id="xy">x: — %, y: — %</span></div>
    </div>

    <div id="controls">
      <button id="send-btn" disabled>Send Point to UGV</button>
      <span class="muted" id="status">Waiting for stream…</span>
    </div>

    <script>
    (async () => {
      const video  = document.getElementById('webrtc');
      const overlay= document.getElementById('overlay');
      const marker = document.getElementById('marker');
      const sendBtn= document.getElementById('send-btn');
      const status = document.getElementById('status');
      const xyText = document.getElementById('xy');

      // --- WebRTC viewer (recvonly) ---
      async function startWebRTC() {
        const pc = new RTCPeerConnection({
          iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }],
        });
        pc.ontrack = (e) => { video.srcObject = e.streams[0]; status.textContent = 'Streaming'; };
        pc.addTransceiver('video', { direction: 'recvonly' });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const res = await fetch('/offer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/sdp' },
          body: offer.sdp
        });
        if (!res.ok) { status.textContent = 'Offer failed'; return; }
        const answerSdp = await res.text();
        await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

        return pc;
      }

      let pc = null;
      try { pc = await startWebRTC(); } catch (e) { console.error(e); status.textContent = 'WebRTC init error'; }

      // --- Click-to-point overlay ---
      let clickedPoint = null;
      function formatPct(v){ return (Math.round(v * 10) / 10).toFixed(1); }

      overlay.addEventListener('click', (e) => {
        const rect = overlay.getBoundingClientRect();
        const xPx = e.clientX - rect.left;
        const yPx = e.clientY - rect.top;
        const xPercent = (xPx / rect.width) * 100;
        const yPercent = (yPx / rect.height) * 100;

        marker.style.left = xPercent + '%';
        marker.style.top  = yPercent + '%';
        marker.style.display = 'block';

        clickedPoint = { xPercent, yPercent };
        sendBtn.disabled = false;
        xyText.textContent = 'x: ' + formatPct(xPercent) + ' %, y: ' + formatPct(yPercent) + ' %';
        status.textContent = 'Point selected';
      });

      sendBtn.addEventListener('click', async () => {
        if (!clickedPoint) return;
        status.textContent = 'Sending...';
        try {
          const res = await fetch('/send-point', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(clickedPoint)
          });
          status.textContent = res.ok ? 'Point sent ✔' : 'Failed to send ✖';
        } catch {
          status.textContent = 'Error sending ✖';
        }
      });
    })();
    </script>
  </body>
</html>`
