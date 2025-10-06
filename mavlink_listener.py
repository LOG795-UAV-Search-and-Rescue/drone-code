from pymavlink import mavutil

master = mavutil.mavlink_connection('udp:0.0.0.0:14550')
print("Listening on UDP:14550...")

while True:
    msg = master.recv_match(blocking=True)
    if msg:
        print(msg.get_type(), msg.to_dict())
