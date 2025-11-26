#!/usr/bin/env python3
import json
import http.client
import urllib.parse
import asyncio
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

WS_CLIENTS = []

INITIAL_YAW = None
def normalize_angle(a):
    while a > 180: a -= 360
    while a < -180: a += 360
    return a

def ws_accept_client(conn):
    try:
        data = conn.recv(1024).decode()
        if "Sec-WebSocket-Key" not in data:
            conn.close()
            return
        key = None
        for line in data.split("\r\n"):
            if "Sec-WebSocket-Key" in line:
                key = line.split(":")[1].strip()
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(hashlib.sha1((key + magic).encode()).digest())
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: " + accept.decode() + "\r\n\r\n"
        )
        conn.send(resp.encode())
        WS_CLIENTS.append(conn)
    except:
        conn.close()

def ws_broadcast(msg):
    frame = b"\x81" + chr(len(msg)).encode() + msg.encode()
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
    print("[WS] WebSocket running on ws://0.0.0.0:8765")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=ws_accept_client, args=(conn,), daemon=True).start()

UI_LISTEN_ADDR = "0.0.0.0:8080"
MEDIAMTX_ORIGIN = "http://127.0.0.1:8889"

STATIC_DIR = Path(__file__).parent / "static"

VIO_CMD = ["sudo", "voxl-inspect-qvio"]

pose_regex = re.compile(r"\|\s*([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\s+([-+]?\d*\.\d+|\d+)\|")
quality_regex = re.compile(r"\|\s*\d+\s*\|\s*(\d+)%")
rpy_regex = re.compile(
    r"\|\s*[-0-9.]+\s+[-0-9.]+\s+[-0-9.]+\|\s*([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\|"
)




HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}

ORIGIN = urllib.parse.urlsplit(MEDIAMTX_ORIGIN)
if ORIGIN.hostname is None:
    raise RuntimeError("MEDIAMTX_ORIGIN must include a hostname")

ORIGIN_HOST = ORIGIN.hostname
ORIGIN_SCHEME = ORIGIN.scheme
ORIGIN_PORT = ORIGIN.port or (443 if ORIGIN_SCHEME == "https" else 80)

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
    def handle_rover_command(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(body.decode("utf-8"))
            cmd = payload.get("cmd", "")
        except:
            cmd = ""
        UDP_IP = "192.168.8.2"
        UDP_PORT = 5005
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(cmd.encode(), (UDP_IP, UDP_PORT))
        resp = "OK sent: " + cmd
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp.encode())

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

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.serve_file("index.html")
            return
        if self.path.startswith("/static/"):
            prefix = "/static/"
            rel = self.path[len(prefix):] if self.path.startswith(prefix) else self.path
            self.serve_file(rel)
            return
        if self.is_whep_path():
            self.proxy_whep()
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/rover-command":
            self.handle_rover_command()
            return

        if self.path == "/api/recalibrate-yaw":
            self.handle_recalibrate_yaw()
            return

        if self.is_whep_path():
            self.proxy_whep()
            return

        if self.path == "/api/call-ugv":
            self.handle_example_call()
            return

        self.send_error(404)


    def do_PATCH(self):
        if self.is_whep_path():
            self.proxy_whep()
            return
        self.send_error(404)

    def is_whep_path(self):
        p = self.path
        return (
            p.startswith("/whep/") or
            p == "/drone/whep" or
            p.startswith("/drone/whep/")
        )

    def serve_file(self, rel):
        fpath = STATIC_DIR / rel
        if not fpath.is_file():
            self.send_error(404)
            return
        if fpath.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif fpath.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif fpath.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        else:
            ctype = "application/octet-stream"
        with open(fpath, "rb") as f:
            data = f.read()
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
                except:
                    pass

    def handle_example_call(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except:
            payload = {}
        resp = json.dumps({"ok": True, "message": "Python server received your request", "received": payload})
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp.encode())
    
    def handle_recalibrate_yaw(self):
        global INITIAL_YAW
        INITIAL_YAW = None  # reset and next VIO reading will set new zero

        resp = json.dumps({"ok": True, "message": "Yaw recalibrated"})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp.encode())



def vio_streamer():
    global INITIAL_YAW

    proc = subprocess.Popen(
        VIO_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, bufsize=1
    )
    print("[VIO] Streaming...")

    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.strip()

            pose_match = pose_regex.search(line)
            quality_match = quality_regex.search(line)
            rpy_match = rpy_regex.search(line)

            # Extract yaw_raw
            if rpy_match:
                roll = float(rpy_match.group(1))
                pitch = float(rpy_match.group(2))
                yaw_raw = float(rpy_match.group(3))
            else:
                yaw_raw = 0.0

           # Initialize yaw reference safely
            if INITIAL_YAW is None:
                if abs(yaw_raw) > 0.1:      # ignore zero / noise until VIO stabilizes
                    INITIAL_YAW = yaw_raw
                else:
                    continue                # skip this frame until yaw is valid

            # Compute calibrated yaw
            yaw = normalize_angle(yaw_raw - INITIAL_YAW)

            if pose_match:
                x = float(pose_match.group(1))
                y = float(pose_match.group(2))
                ts = time.time()
                quality = quality_match.group(1) if quality_match else "-"

                packet = "%0.3f,%0.3f,%0.3f,%0.1f,%s" % (ts, x, y, yaw, quality)

                ws_broadcast(packet)

                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.sendto(packet.encode(), ("192.168.8.2", 5005))

    except Exception as e:
        print("[VIO ERROR]", e)
    finally:
        try:
            proc.terminate()
        except PermissionError:
            print("[VIO] Cannot terminate VIO subprocess (no permissions).")
        except Exception as e:
            print("[VIO] Terminate error:", e)



def rover_udp_listener():
    """
    Listen on UDP 5006 for rover pose packets and forward them to WebSocket clients.
    Packets are expected in this format:
        ROVER,x,y,o
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 5006))
    print("[ROVER UDP] Listening on 0.0.0.0:5006")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8", errors="ignore").strip()
            # Example: "ROVER,-0.005,0.000,-3.071"
            ws_broadcast(msg)
        except Exception as e:
            print("[ROVER UDP ERROR]", e)

def main():
    host, port = UI_LISTEN_ADDR.split(":")
    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    print("UI listening on %s" % UI_LISTEN_ADDR)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("Stopped.")

if __name__ == "__main__":
    # WebSocket server for the browser
    threading.Thread(target=start_ws_server, daemon=True).start()
    # Drone VIO streamer (voxl-inspect-qvio)
    threading.Thread(target=vio_streamer, daemon=True).start()
    # NEW: Rover pose listener (UDP 5006 → WebSocket)
    threading.Thread(target=rover_udp_listener, daemon=True).start()

    # HTTP UI server
    main()
