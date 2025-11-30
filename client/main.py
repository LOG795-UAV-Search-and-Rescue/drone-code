#!/usr/bin/env python3
import json
import http.client
import urllib.parse
import threading
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
latest_drone_local = (0.0, 0.0, 0.0)  # dx, dy, yaw (deg)
latest_rover_x = 0.0
latest_rover_y = 0.0
latest_rover_o = 0.0

# 3-point calibration storage
A = None
B = None
C = None

CALIBRATED = False

# Final transform for UI only: world = R * local + T
R = [[1,0],[0,1]]
T = (0,0)

# ============================================================
# WEBSOCKET SERVER
# ============================================================
WS_CLIENTS = []

def build_ws_frame(msg):
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
        conn.close()

def ws_broadcast(msg):
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
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 8765))
    s.listen(5)
    print("[WS] Listening on ws://0.0.0.0:8765")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=ws_accept_client, args=(conn,), daemon=True).start()

# ============================================================
# HTTP SERVER (unchanged)
# ============================================================

UI_LISTEN_ADDR = "0.0.0.0:8080"
STATIC_DIR = Path(__file__).parent / "static"

MEDIAMTX_ORIGIN = "http://127.0.0.1:8889"
ORIGIN = urllib.parse.urlsplit(MEDIAMTX_ORIGIN)
ORIGIN_HOST = ORIGIN.hostname
ORIGIN_PORT = ORIGIN.port or 80

HOP_BY_HOP = {
    "connection","keep-alive","proxy-authenticate","proxy-authorization",
    "te","trailers","transfer-encoding","upgrade"
}

def filter_headers(h):
    return {k:v for k,v in h.items() if k.lower() not in HOP_BY_HOP and k.lower()!="host"}

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):

    # ---------------------- CALIBRATION ----------------------
    def do_POST(self):
        if self.path == "/api/calib/start": return self.calib_A()
        if self.path == "/api/calib/right": return self.calib_B()
        if self.path == "/api/calib/forward": return self.calib_C()
        if self.path == "/api/calib/finish": return self.calib_finish()
        if self.path == "/api/rover-command": return self.send_rover_cmd()
        self.send_error(404)

    def do_GET(self):
        if self.path in ("/","/index.html"):
            return self.serve_file("index.html")
        if self.path.startswith("/static/"):
            return self.serve_file(self.path[8:])
        self.send_error(404)

    def calib_A(self):
        global A
        A = latest_drone_local
        ws_broadcast(f"CALIB_A,{A[0]},{A[1]}")
        return self._ok("Saved A")

    def calib_B(self):
        global B
        B = latest_drone_local
        ws_broadcast(f"CALIB_B,{B[0]},{B[1]}")
        return self._ok("Saved B")

    def calib_C(self):
        global C
        C = latest_drone_local
        ws_broadcast(f"CALIB_C,{C[0]},{C[1]}")
        return self._ok("Saved C")

    def calib_finish(self):
        global A,B,C,R,T,CALIBRATED

        if A is None or B is None or C is None:
            return self._ok("ERR Missing A/B/C")

        Ax,Ay,_ = A
        Bx,By,_ = B
        Cx,Cy,_ = C

        # Compute right (+X)
        vx = (Bx-Ax, By-Ay)
        ln = math.hypot(*vx)
        ux = (vx[0]/ln, vx[1]/ln)

        # Compute forward (+Y)
        vy = (Cx-Ax, Cy-Ay)
        ln = math.hypot(*vy)
        uy = (vy[0]/ln, vy[1]/ln)

        R = [
            [ux[0], uy[0]],
            [ux[1], uy[1]]
        ]

        T = (
            -Ax*R[0][0] - Ay*R[0][1],
            -Ax*R[1][0] - Ay*R[1][1]
        )

        CALIBRATED = True
        ws_broadcast(f"CALIB_DONE,{R[0][0]},{R[0][1]},{R[1][0]},{R[1][1]},{T[0]},{T[1]}")
        return self._ok("Calibration complete")

    # ---------------------- ROVER COMMAND ----------------------
    def send_rover_cmd(self):
        length=int(self.headers.get("Content-Length",0))
        raw=self.rfile.read(length)
        payload=json.loads(raw.decode())
        cmd=payload.get("cmd","")

        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.sendto(cmd.encode(),("192.168.8.2",5005))
        sock.close()
        return self._ok("Sent")

    # ---------------------- UTIL ----------------------
    def _ok(self,msg):
        msg_b = msg.encode()
        self.send_response(200)
        self.send_header("Content-Length", len(msg_b))
        self.end_headers()
        self.wfile.write(msg_b)

    def serve_file(self,rel):
        p=STATIC_DIR/rel
        if not p.exists(): return self.send_error(404)
        data=p.read_bytes()
        mime={".html":"text/html",".css":"text/css",".js":"application/javascript"}.get(p.suffix,"application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",len(data))
        self.end_headers()
        self.wfile.write(data)

# ============================================================
# VIO STREAMER (where the FIX happens)
# ============================================================

pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
rpy_regex = re.compile(
    r"\|\s*[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\|\s*([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\|"
)
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")

INITIAL_X=None
INITIAL_Y=None
INITIAL_YAW=None

def normalize_angle(a):
    while a>180: a-=360
    while a<-180: a+=360
    return a

def restart_voxl_services():
    print("[INIT] Restarting VOXL localization services...")
    subprocess.call(["sudo", "systemctl", "restart",
                     "voxl-qvio-server", "voxl-vision-px4", "voxl-px4"])

    # Give the services a moment to reboot
    time.sleep(5)

    # Wait until QVIO is actually running again
    print("[INIT] Waiting for voxl-qvio-server to come online...")
    for i in range(20):
        status = subprocess.getoutput("systemctl is-active voxl-qvio-server")
        if "active" in status:
            print("[INIT] QVIO is active.")
            return
        time.sleep(0.5)

    print("[WARNING] QVIO did not become active in time.")


def vio_streamer():
    global latest_drone_local, INITIAL_X, INITIAL_Y, INITIAL_YAW, CALIBRATED

    vio = subprocess.Popen(
        ["sudo","voxl-inspect-qvio"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, bufsize=1
    )

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print("[VIO] Streaming...")

    while True:
        line = vio.stdout.readline()
        if not line: break
        line=line.strip()

        pose=pose_regex.search(line)
        rpy=rpy_regex.search(line)
        q=quality_regex.search(line)

        if not pose or not rpy:
            continue

        raw_x=float(pose.group(1))
        raw_y=float(pose.group(2))
        yaw_raw=float(rpy.group(3))

        if INITIAL_Y is None:
            INITIAL_X=raw_x
            INITIAL_Y=raw_y

        if INITIAL_YAW is None:
            if abs(yaw_raw)>0.1:
                INITIAL_YAW=yaw_raw
            else:
                continue

        dx = raw_x - INITIAL_X
        dy = raw_y - INITIAL_Y
        yaw = normalize_angle(yaw_raw - INITIAL_YAW)

        latest_drone_local = (dx, dy, yaw)

        # ---- Compute world coords for UI only ----
        if CALIBRATED:
            world_x = R[0][0]*dx + R[0][1]*dy + T[0]
            world_y = R[1][0]*dx + R[1][1]*dy + T[1]
        else:
            world_x, world_y = dx, dy

        ts=time.time()
        quality = q.group(1) if q else "-"

        # ------------------------------
        # Send WORLD coords to UI
        # ------------------------------
        ws_broadcast(f"{ts:.3f},{world_x:.3f},{world_y:.3f},{yaw:.3f},{quality}")

        # ------------------------------
        # Send LOCAL coords to rover
        # ------------------------------
        rover_packet = f"{ts:.3f},{world_x:.3f},{world_y:.3f},{quality}"
        udp.sendto(rover_packet.encode(), ("192.168.8.2", 5005))

# ============================================================
# ROVER UDP LISTENER
# ============================================================

def rover_udp_listener():
    global latest_rover_x, latest_rover_y, latest_rover_o

    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0",5006))
    print("[ROVER] Listening on :5006")

    while True:
        msg,_=sock.recvfrom(1024)
        msg=msg.decode().strip()

        if msg.startswith("ROVER"):
            p=msg.split(",")
            latest_rover_x=float(p[1])
            latest_rover_y=float(p[2])
            latest_rover_o=float(p[3])

        ws_broadcast(msg)

# ============================================================
# LOG THREAD
# ============================================================

def log_thread():
    while True:
        time.sleep(5)
        dx,dy,yaw = latest_drone_local
        print("\n===== STATUS =====")
        print(f"Drone Local:   x={dx:.2f}, y={dy:.2f}, yaw={yaw:.2f}")
        print(f"Rover:         x={latest_rover_x:.2f}, y={latest_rover_y:.2f}, o={latest_rover_o:.2f}")
        print(f"R matrix:      {R}")
        print(f"T vector:      {T}")
        print("==================\n")

# ============================================================
# MAIN
# ============================================================

def main():
    host,port=UI_LISTEN_ADDR.split(":")
    httpd=ThreadingHTTPServer((host,int(port)),Handler)
    print("[HTTP] Listening on",UI_LISTEN_ADDR)
    httpd.serve_forever()

if __name__=="__main__":
    restart_voxl_services()

    threading.Thread(target=start_ws_server,daemon=True).start()
    threading.Thread(target=vio_streamer,daemon=True).start()
    threading.Thread(target=rover_udp_listener,daemon=True).start()
    threading.Thread(target=log_thread,daemon=True).start()
    main()
