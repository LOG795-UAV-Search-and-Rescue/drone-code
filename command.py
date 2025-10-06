import requests

JETSON_IP = "192.168.x.x"  # whatever IP the Jetson has
resp = requests.post(
    f"http://{JETSON_IP}:8080/hotspot",
    json={"action": "start"}
)
print(resp.json())