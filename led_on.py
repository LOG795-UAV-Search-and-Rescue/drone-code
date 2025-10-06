import requests
import urllib.parse

ROBOT_IP = "192.168.4.1"

# JSON command to turn LEDs fully ON
command = {"T": 132, "IO4": 255, "IO5": 255}

# Convert dict → JSON string
import json
cmd_str = json.dumps(command)

# Encode JSON so it fits in the URL
encoded_cmd = urllib.parse.quote(cmd_str)

url = f"http://{ROBOT_IP}/js?json={encoded_cmd}"
print("Sending:", url)

response = requests.get(url)
print("Response:", response.text)