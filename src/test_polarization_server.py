from zmqhelper import Client
import json

con = Client(ip='bellamd1.campus.nist.gov', port=5100)

def send_message(con, cmd, params=None, timeout=10000):
    if params is None:
        params = {}
    message_to_send = json.dumps({"cmd": cmd, "params": {**params}})
    resp = con.send_message(message_to_send, timeout=timeout)
    return resp

# con = Client(ip='localhost', port=5565)
# send_message(con, 'set_polarization', {'setting': "b_calib"})
# send_message(con, 'set_polarization', {'setting': "b_calib", 'use_cache':False, 'update_cache':True})

#'{"message": {"1": {"cmd": "set_polarization:str", "description": "Set the waveplates to select a particular path in the experiment. The command get_paths will return all valid paths. Results are cached. You can optionally override or update the cache.", "params": {"setting": "which_path_to_use:str", "update_cache": "optional:bool", "use_cahce": "optional:bool,"}}, "2": {"cmd": "set_power:str", "description": "Set the power of the source.", "params": {"power": "Number between 0 and 1:float"}}, "3": {"cmd": "set_pc_to_bell_angles:str", "description": "Set the pockels cell to select a particular path in the experiment. If no angles are provided, the default values stored on the server are used. The command get_paths will return all valid paths. Results are cached. You can optionally override or update the cache.", "params": {"angles": "optional:[angle_1:float, angle_2:float, angle_3:float]", "update_cache": "optional:bool", "use_cahce": "optional:bool,"}}, "4": {"cmd": "get_paths:str", "description": "Get all valid paths in the experiment."}, "5": {"cmd": "home:str", "description": "Home the Pockels cells. The party can be either alice, bob, source, or all.", "params": {"party": "party:str,"}}, "6": {"cmd": "calibrate:str", "description": "Calibrate the waveplates. Valid parties are alice, bob, or source. Choosing alice or bob will move the waveplates designed to correct polarization errors in the fibers going from the source to alice/bob. Choosing source calibrates the waveplates used to correct the polarization drift in the fiber that the pump laser is coupled into.", "params": {"party": "party:str,"}}, "7": {"cmd": "commands:str", "description": "Get all commands available on the server."}, "8": {"cmd": "status:str", "description": "Get the status of the server."}}}'