#!/usr/bin/env python3
import json
import http.client
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path

UI_LISTEN_ADDR = "0.0.0.0:8080"
MEDIAMTX_ORIGIN = "http://127.0.0.1:8889"

STATIC_DIR = Path(__file__).parent / "static"

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

    def is_whep_path(self) -> bool:
        p = self.path
        return (
            p.startswith("/whep/") or
            p == "/drone/whep" or
            p.startswith("/drone/whep/")
        )

    def serve_file(self, rel: str):
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
        path = incoming.path

        if path == "/drone/whep":
            path = "/whep"
        elif path.startswith("/drone/whep/"):
            path = "/whep" + path[len("/drone/whep"):]

        target_url = ORIGIN._replace(path=path, query=incoming.query or "").geturl()

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

    def handle_example_call(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        resp = {
            "ok": True,
            "message": "Python server received your request",
            "received": payload,
        }
        data = json.dumps(resp).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    address = UI_LISTEN_ADDR.split(":")
    host = address[0]
    port = int(address[1])
    httpd = ThreadingHTTPServer((host, port), Handler)
    print("UI listening on %s" % UI_LISTEN_ADDR)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("Stopped.")


if __name__ == "__main__":
    main()
