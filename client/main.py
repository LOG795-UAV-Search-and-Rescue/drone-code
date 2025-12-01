#!/usr/bin/env python3
import json
import http.client
import urllib.parse
import threading
import argparse
import subprocess
import re
import time
import socket
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path
import math


# ============================================================
# GLOBAL STATE
# ============================================================
# Quick note: I'm a student so I kept things global for simplicity.
# It's not the cleanest design, but it's easier to reason about for this project.
latest_drone_local = (0.0, 0.0, 0.0)  # dx, dy, yaw (deg) - local output coming from VOXL
latest_rover_x = 0.0  # rover-reported x
latest_rover_y = 0.0  # rover-reported y
latest_rover_o = 0.0  # rover orientation (heading)

# 3-point calibration storage (A,B,C) used to compute UI world transform
A = None
B = None
C = None

CALIBRATED = False  # flag used to switch between local and calibrated world coords

# Final transform for UI only: world = R * local + T
# R is a 2x2 matrix, T is a 2-vector. Initially identity transform.
R = [[1,0],[0,1]]
T = (0,0)


# ============================================================
# WEBSOCKET SERVER
# ============================================================
# A really minimal websocket implementation: handshake + unmasked frames
WS_CLIENTS = []

def build_ws_frame(msg):
    # Create a small unmasked text frame (client -> server masking not needed for server->client)
    payload = msg.encode()
    L = len(payload)
    if L < 126:
        header = bytes([0x81, L])
    elif L < 65536:
        header = bytes([0x81, 126]) + L.to_bytes(2, 'big')
    else:
        header = bytes([0x81, 127]) + L.to_bytes(8, 'big')
    return header + payload

def ws_accept_client(conn):
    # Basic (insecure) websocket handshake - parses Sec-WebSocket-Key, returns Sec-WebSocket-Accept
    try:
        hdr = conn.recv(2048).decode()
        key = ""
        for line in hdr.split("\r\n"):
            if "Sec-WebSocket-Key" in line:
                key = line.split(":")[1].strip()
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(
            hashlib.sha1((key + magic).encode()).digest()
        ).decode()

        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: " + accept + "\r\n\r\n"
        )
        conn.send(resp.encode())
        WS_CLIENTS.append(conn)
    except:
        # If handshake fails, close the socket and move on.
        conn.close()

def ws_broadcast(msg):
    # Broadcast a string to all connected web socket clients.
    frame = build_ws_frame(msg)
    dead = []
    for c in WS_CLIENTS:
        try:
            c.send(frame)
        except:
            dead.append(c)
    for d in dead:
        WS_CLIENTS.remove(d)

def start_ws_server():
    # Simple single-threaded accept loop; each new connection's handshake runs in a separate thread
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 8765))
    s.listen(5)
    print("[WS] Listening on ws://0.0.0.0:8765")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=ws_accept_client, args=(conn,), daemon=True).start()


# ============================================================
# HTTP SERVER
# ============================================================

UI_LISTEN_ADDR = "0.0.0.0:8080"
STATIC_DIR = Path(__file__).parent / "static"

MEDIAMTX_ORIGIN = "http://127.0.0.1:8889"
ORIGIN = urllib.parse.urlsplit(MEDIAMTX_ORIGIN)
if ORIGIN.hostname is None:
    raise RuntimeError("MEDIAMTX_ORIGIN must include a hostname")

ORIGIN_HOST = ORIGIN.hostname
ORIGIN_SCHEME = ORIGIN.scheme
ORIGIN_PORT = ORIGIN.port or (443 if ORIGIN_SCHEME == "https" else 80)

# Hop-by-hop headers we should drop when proxying - not used heavily, but good to know.
HOP_BY_HOP = {
    "connection","keep-alive","proxy-authenticate","proxy-authorization",
    "te","trailers","transfer-encoding","upgrade"
}

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def filter_headers(headers):
    out = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP or lk == "host":
            continue
        out[k] = v
    return out

class Handler(BaseHTTPRequestHandler):
    rover_ip = None

    def do_OPTIONS(self):
        if self.is_whep_path():
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type,If-None-Match,If-Match")
            self.end_headers()
            return
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        # Map POST endpoints to handlers. Kept super explicit for clarity.
        if self.path == "/api/calib/start": return self.calib_A()
        if self.path == "/api/calib/right": return self.calib_B()
        if self.path == "/api/calib/forward": return self.calib_C()
        if self.path == "/api/calib/finish": return self.calib_finish()
        if self.path == "/api/rover-command": return self.send_rover_cmd()
        if self.is_whep_path(): return self.proxy_whep()
        self.send_error(404)

    def do_GET(self):
        if self.path in ("/","/index.html"):
            return self.serve_file("index.html")
        if self.path.startswith("/static/"):
            return self.serve_file(self.path[8:])
        if self.is_whep_path():
            return self.proxy_whep()
        self.send_error(404)
    
    def do_PATCH(self):
        if self.is_whep_path():
            return self.proxy_whep()
        self.send_error(404)

    def is_whep_path(self):
        p = self.path
        return (
            p.startswith("/whep/") or
            p == "/drone/whep" or
            p.startswith("/drone/whep/")
        )

    def calib_A(self):
        # Save the current drone local pose as calibration point A
        global A
        A = latest_drone_local
        ws_broadcast(f"CALIB_A,{A[0]},{A[1]}")
        return self._ok("Saved A")

    def calib_B(self):
        # Save the current drone local pose as calibration point B
        global B
        B = latest_drone_local
        ws_broadcast(f"CALIB_B,{B[0]},{B[1]}")
        return self._ok("Saved B")

    def calib_C(self):
        # Save the current drone local pose as calibration point C
        global C
        C = latest_drone_local
        ws_broadcast(f"CALIB_C,{C[0]},{C[1]}")
        return self._ok("Saved C")

    def calib_finish(self):
        # Compute a simple 2D transform (rotation+translation) with A as origin, ux from A->B,
        # uy from A->C. This is a bit naive (no orthonormalization), but works OK for UI mapping.
        global A,B,C,R,T,CALIBRATED

        if A is None or B is None or C is None:
            # We don't throw 400; just tell the UI we need all points
            return self._ok("ERR Missing A/B/C")

        Ax,Ay,_ = A
        Bx,By,_ = B
        Cx,Cy,_ = C

        # x-axis: from A to B
        vx = (Bx-Ax, By-Ay)
        ln = math.hypot(*vx)
        ux = (vx[0]/ln, vx[1]/ln)

        # y-axis: from A to C
        vy = (Cx-Ax, Cy-Ay)
        ln = math.hypot(*vy)
        uy = (vy[0]/ln, vy[1]/ln)

        # R is column major-style here: columns are ux and uy
        R = [
            [ux[0], uy[0]],
            [ux[1], uy[1]]
        ]

        # T: translate so that world-origin sits at A
        T = (
            -Ax*R[0][0] - Ay*R[0][1],
            -Ax*R[1][0] - Ay*R[1][1]
        )

        CALIBRATED = True
        # Notify the UI with the matrix and vector (so they can compute properly)
        ws_broadcast(f"CALIB_DONE,{R[0][0]},{R[0][1]},{R[1][0]},{R[1][1]},{T[0]},{T[1]}")
        return self._ok("Calibration complete")

    def send_rover_cmd(self):
        # Receive JSON payloads (like {"cmd": "STOP"}), forward command via UDP to rover
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode())
        cmd = payload.get("cmd", "")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(cmd.encode(), (self.rover_ip, 5005))
        sock.close()
        return self._ok("Sent")

    def _ok(self,msg):
        # Helper: send a simple text response with status 200
        msg_b = msg.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(msg_b)))
        self.end_headers()
        self.wfile.write(msg_b)

    def serve_file(self,rel):
        # Serve a file from the static dir. No security checks — fine for our local dev use.
        p = STATIC_DIR / rel
        if not p.exists(): return self.send_error(404)

        data = p.read_bytes()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8"
        }.get(p.suffix, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    
    def proxy_whep(self):
        incoming = urllib.parse.urlsplit(self.path)
        target_url = ORIGIN._replace(
            path=incoming.path,
            query=incoming.query or ""
        ).geturl()

        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else None

        conn = None
        try:
            if ORIGIN_SCHEME == "https":
                conn = http.client.HTTPSConnection(ORIGIN_HOST, ORIGIN_PORT, timeout=20)
            else:
                conn = http.client.HTTPConnection(ORIGIN_HOST, ORIGIN_PORT, timeout=20)

            conn.request(self.command, target_url, body=body, headers=filter_headers(self.headers))
            resp = conn.getresponse()

            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() in HOP_BY_HOP:
                    continue
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except Exception as e:
            self.send_error(502, "MediaMTX upstream error: %s" % e)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

# ============================================================
# VIO STREAMER (where the FIX happens)
# ============================================================
# This spawns "voxl-inspect-qvio" and parses its stdout. The code
# extracts x,y and yaw, converts to a local relative frame using an initial
# offset, and broadcasts both to the UI and the rover over UDP.
pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
rpy_regex = re.compile(
    r"\|\s*[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\|\s*([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\|"
)
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

INITIAL_X=None  # Starting offset so we don't use absolute world coords
INITIAL_Y=None
INITIAL_YAW=None

def normalize_angle(a):
    # Keep angles between -180 and 180 for nicer UI
    while a>180: a-=360
    while a<-180: a+=360
    return a

def restart_voxl_services():
    # VOXL services need restarting sometimes; convenience function.
    # TODO: Could add a check to only restart if necessary.
    subprocess.call(["sudo", "systemctl", "restart",
                     "voxl-qvio-server", "voxl-vision-px4", "voxl-px4"])

    # Give the services a moment to reboot
    time.sleep(5)

    # Wait until QVIO is actually running again
    for i in range(20):
        status = subprocess.getoutput("systemctl is-active voxl-qvio-server")
        if "active" in status:
            print("[INIT] QVIO is active.")
            return
        time.sleep(0.5)

    # If not active by now we've got bigger problems (but the function will just continue).


def vio_streamer(roverIp):
    # This is the meat: parse output, track initial offsets, compute local coords,
    # optionally map to world coords if calibration is done, then broadcast.
    global latest_drone_local, INITIAL_X, INITIAL_Y, INITIAL_YAW, CALIBRATED

    vio = subprocess.Popen(
        ["sudo", "voxl-inspect-qvio"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, bufsize=1
    )

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        line = vio.stdout.readline()
        if not line: break
        line=line.strip()

        # The parser is pretty lax; it looks for the patterns and skips any non-match lines
        pose=pose_regex.search(line)
        rpy=rpy_regex.search(line)
        q=quality_regex.search(line)

        # If we don't have a full pose+orientation, ignore this line.
        if not pose or not rpy:
            continue

        raw_x = float(pose.group(1))
        raw_y = float(pose.group(2))
        yaw_raw = float(rpy.group(3))

        # Initialize offsets from the first good reading
        if INITIAL_Y is None:
            INITIAL_X = raw_x
            INITIAL_Y = raw_y

        if INITIAL_YAW is None:
            # yaw might be noisy at startup; don't set until it seems plausible
            if abs(yaw_raw) > 0.1:
                INITIAL_YAW = yaw_raw
            else:
                continue

        # Compute local displacement and normalized yaw relative to the initial pose
        dx = raw_x - INITIAL_X
        dy = raw_y - INITIAL_Y
        yaw = normalize_angle(yaw_raw - INITIAL_YAW)

        latest_drone_local = (dx, dy, yaw)

        # Compute world coords for the UI only if the operator did a calibration
        if CALIBRATED:
            world_x = R[0][0]*dx + R[0][1]*dy + T[0]
            world_y = R[1][0]*dx + R[1][1]*dy + T[1]
        else:
            world_x, world_y = dx, dy

        ts=time.time()
        quality = q.group(1) if q else "-"

        # Send WORLD coords to UI via websocket
        ws_broadcast(f"{ts:.3f},{world_x:.3f},{world_y:.3f},{yaw:.3f},{quality}")

        # Send LOCAL coords to rover (we use world_x here so rover and UI are consistent)
        rover_packet = f"{ts:.3f},{world_x:.3f},{world_y:.3f},{quality}"
        udp.sendto(rover_packet.encode(), (roverIp, 5005))


# ============================================================
# ROVER UDP LISTENER
# ============================================================
# Listens for packets from the rover and updates the latest_rover_* globals,
# also rebroadcasts the message to any websocket clients.
def rover_udp_listener():
    global latest_rover_x, latest_rover_y, latest_rover_o

    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0",5006))
    print("[ROVER] Listening on :5006")

    while True:
        msg,_=sock.recvfrom(1024)
        msg=msg.decode().strip()

        if msg.startswith("ROVER"):
            p = msg.split(",")
            latest_rover_x = float(p[1])
            latest_rover_y = float(p[2])
            latest_rover_o = float(p[3])

        # Rebroadcast all rover messages to UI
        ws_broadcast(msg)


# ============================================================
# LOG THREAD
# ============================================================
# Simple periodic status dump originally used for debugging.
def log_thread():
    while True:
        time.sleep(10)  # Increase sleep time to reduce log frequency
        dx, dy, yaw = latest_drone_local
        # Reduced logging to avoid performance issues
        # print("\n===== STATUS =====")
        # print(f"Drone Local:   x={dx:.2f}, y={dy:.2f}, yaw={yaw:.2f}")
        # print(f"Rover:         x={latest_rover_x:.2f}, y={latest_rover_y:.2f}, o={latest_rover_o:.2f}")
        # print(f"R matrix:      {R}")
        # print(f"T vector:      {T}")
        # print("==================\n")


# ============================================================
# MAIN
# ============================================================
def main():
    host, port = UI_LISTEN_ADDR.split(":")
    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    print("[HTTP] Listening on", UI_LISTEN_ADDR)
   
    httpd.serve_forever()

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--roverIp",
        "-ri",
        type=str,
        default="192.168.8.2",
        help="IP address of the device"
    )
    args = parser.parse_args()
    Handler.rover_ip = args.roverIp

    # On startup, restart QVIO services (needed for VOXL). Not ideal for dev workflow,
    # but helps keep things consistent when running on the actual hardware.
    restart_voxl_services()

    # Spawn the various service threads. I use daemon threads so it will exit cleanly
    # when the main thread (HTTP server) stops.
    threading.Thread(target=start_ws_server, daemon=True).start()
    threading.Thread(target=vio_streamer, args=(args.roverIp,), daemon=True).start()
    threading.Thread(target=rover_udp_listener, daemon=True).start()
    threading.Thread(target=log_thread, daemon=True).start()
    main()
