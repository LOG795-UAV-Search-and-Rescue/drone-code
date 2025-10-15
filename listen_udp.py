import socket

UDP_IP = "0.0.0.0"  # Listen on all network interfaces
UDP_PORT = 5005

print(f"[PC ✅] Listening for UDP packets on port {UDP_PORT}...")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

try:
    while True:
        data, addr = sock.recvfrom(1024)  # buffer size
        print(f"[RECV] {data.decode().strip()}")
except KeyboardInterrupt:
    print("\n[PC] Stopped.")
finally:
    sock.close()
