import requests
import argparse
import urllib.parse

def main():
    parser = argparse.ArgumentParser(description='Http JSON Communication')
    parser.add_argument('ip', type=str, help='IP address of the robot, e.g. 192.168.4.1')
    args = parser.parse_args()

    ip_addr = args.ip

    try:
        while True:
            command = input("Enter JSON command (e.g. {\"T\":1,\"L\":0.5,\"R\":0.5}): ")
            # Encode the JSON so it can be safely added to URL
            encoded_cmd = urllib.parse.quote(command)
            url = f"http://{ip_addr}/js?json={encoded_cmd}"
            response = requests.get(url)
            print("Response:", response.text)
    except KeyboardInterrupt:
        print("\nStopped by user.")

if __name__ == "__main__":
    main()
