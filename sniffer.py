# save as sniff_mavlink.py and run: python sniff_mavlink.py
from pymavlink import mavutil
from time import time

m = mavutil.mavlink_connection('udp:0.0.0.0:14550')
seen = {}
print("Listening on UDP:14550 for 10 seconds...")
t0 = time()
while time() - t0 < 10:
    msg = m.recv_match(blocking=False)
    if not msg:
        continue
    t = msg.get_type()
    seen[t] = seen.get(t, 0) + 1

print("\nMessage types received (top 30):")
for k, v in sorted(seen.items(), key=lambda kv: -kv[1])[:30]:
    print(f"{k:30s} {v}")
