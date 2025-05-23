from zmqhelper import Client
import json

con = Client(ip='localhost', port=5100)

def send_message(con, cmd, params=None):
    if params is None:
        params = {}
    message_to_send = json.dumps({"cmd": cmd, "params": {**params}})
    resp = con.send_message(message_to_send)
    return resp

# send_message(con, 'set_polarization', {'setting': "b_calib"})
# send_message(con, 'set_polarization', {'setting': "b_calib", 'use_cache':False, 'update_cache':True})