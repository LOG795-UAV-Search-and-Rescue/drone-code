package ui

const htmlUI = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Drone Control UI</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { color-scheme: dark; }
    body {
      background: #0f1115; color: #e8e8e8; margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      display: flex; flex-direction: column; align-items: center; padding: 16px;
    }
    h2 { margin: 8px 0 12px; font-weight: 600; }
    #video-container {
      position: relative; display: inline-block; border: 1px solid #2a2f3a;
      border-radius: 10px; overflow: hidden; max-width: 95vw;
      box-shadow: 0 6px 22px rgba(0,0,0,.35);
    }
    #video-feed {
      max-width: 95vw; height: auto; display: block; cursor: crosshair; background:#000;
    }
    #marker {
      position: absolute; width: 12px; height: 12px; background: #ff3b3b;
      border: 2px solid #fff; border-radius: 50%; transform: translate(-50%, -50%);
      pointer-events: none; display: none; box-shadow: 0 0 10px rgba(255,59,59,.8);
    }
    #hud {
      position: absolute; left: 10px; bottom: 10px; background: rgba(15,17,21,.65);
      padding: 6px 10px; border-radius: 8px; font-size: 12px;
    }
    #controls { margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap; }
    button {
      background: #1a73e8; color: white; border: none; padding: 10px 16px;
      border-radius: 8px; cursor: pointer; font-weight: 600;
    }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .muted { opacity: .7; font-size: 12px; }
    .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:8px; }
    input[type="text"] {
      background:#0d0f14; border:1px solid #2a2f3a; color:#e8e8e8; padding:8px 10px; border-radius:8px; width: 280px;
    }
  </style>
</head>
<body>
  <h2>Drone Live Feed</h2>

  <div class="row">
    <label class="muted">Stream URL</label>
    <input id="stream-url" type="text" value="http://192.168.8.1:8080/video" />
    <button id="apply-src">Apply</button>
  </div>

  <div id="video-container">
    <img id="video-feed" src="http://192.168.8.1:8080/video" alt="Live video">
    <div id="marker"></div>
    <div id="hud"><span id="xy">x: — %, y: — %</span></div>
  </div>

  <div id="controls">
    <button id="send-btn" disabled>Send Point to UGV</button>
    <span class="muted" id="status">No point selected</span>
  </div>

<script>
  const video  = document.getElementById('video-feed');
  const marker = document.getElementById('marker');
  const sendBtn= document.getElementById('send-btn');
  const status = document.getElementById('status');
  const xyText = document.getElementById('xy');
  const urlInp = document.getElementById('stream-url');
  const apply  = document.getElementById('apply-src');

  let clickedPoint = null;

  function formatPct(v){ return (Math.round(v * 10) / 10).toFixed(1); }

  video.addEventListener('click', (e) => {
    const rect = video.getBoundingClientRect();
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
    console.log('[UI] Selected point', clickedPoint);
  });

  sendBtn.addEventListener('click', async () => {
    if (!clickedPoint) return;
    status.textContent = 'Sending...';

    try {
      const res = await fetch('/send-point', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(clickedPoint)
      });
      if (res.ok) {
        status.textContent = 'Point sent ✔';
      } else {
        status.textContent = 'Failed to send ✖';
      }
    } catch (err) {
      console.error(err);
      status.textContent = 'Error sending ✖';
    }
  });

  apply.addEventListener('click', () => {
    const u = urlInp.value.trim();
    if (!u) return;
    // Reload the <img> to reset the stream
    video.src = '';
    setTimeout(() => { video.src = u; }, 50);
  });
</script>
</body>
</html>`
