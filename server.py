from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route("/hotspot", methods=["POST"])
def hotspot():
    data = request.get_json()
    if not data: 
        return {"error": "No JSON"}, 400

    action = data.get("action")
    if action == "start":
        try:
            # Bring up 5G modem (assumes profile already created)
            subprocess.run(["nmcli", "connection", "up", "5g-conn"], check=True)

            # Start WiFi hotspot
            subprocess.run([
                "nmcli", "device", "wifi", "hotspot",
                "ifname", "wlan0",
                "ssid", "RoverHotspot",
                "password", "rover12345"
            ], check=True)

            # Enable NAT
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], check=True)
            subprocess.run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", "wwan0", "-j", "MASQUERADE"], check=True)

            return {"status": "hotspot started"}
        except subprocess.CalledProcessError as e:
            return {"error": str(e)}, 500

    elif action == "stop":
        subprocess.run(["nmcli", "connection", "down", "5g-conn"])
        return {"status": "hotspot stopped"}

    return {"error": "Invalid action"}, 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
