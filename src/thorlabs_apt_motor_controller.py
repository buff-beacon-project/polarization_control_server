# motor_controller.py
from threading import Thread
from zmqhelper import Client

class MotorController(Thread):
    """
    A threaded motor-control client that sends commands
    via a ZMQ REQ/REP socket with built-in timeouts.
    """
    def __init__(self, ip, port):
        super().__init__()
        self.client = Client(ip, port)
        # build name→ID map
        self.id_dict = {}
        try:
            self.get_name(timeout=2000)
        except RuntimeError as e:
            raise ConnectionError(f"Could not connect to motor {ip}:{port}: {e}")
        # self.get_name(timeout=2000)  # uses default timeout

    def _send_and_recv(self, cmd: str, timeout: int = None) -> str:
        """
        Helper: send `cmd`, return response or 'Timeout'.
        If timeout is None, Client.send_message uses its own default.
        """
        # append newline and forward the timeout
        if timeout is None:
            return self.client.send_message(cmd + "\n")
        else:
            return self.client.send_message(cmd + "\n", timeout)

    def get_name(self, timeout: int = None) -> dict:
        """Populate `self.id_dict` from the 'apt' command."""
        resp = self._send_and_recv("apt", timeout)
        if resp == "Timeout":
            raise RuntimeError("Failed to get motor names (timeout)")
        names = resp.rstrip(",\n").split(",")
        self.id_dict = {name: idx for idx, name in enumerate(names)}
        return self.id_dict

    def forward(self, name: str, distance: int, timeout: int = None) -> str:
        """Move motor `name` forward by `distance` units."""
        try:
            idx = self.id_dict[name]
            cmd = f"for {distance} {idx}"
        except KeyError:
            return "Motor not connected"
        return self._send_and_recv(cmd, timeout)

    def backward(self, name: str, distance: int, timeout: int = None) -> str:
        """Move motor `name` backward by `distance` units."""
        try:
            idx = self.id_dict[name]
            cmd = f"back {distance} {idx}"
        except KeyError:
            return "Motor not connected"
        return self._send_and_recv(cmd, timeout)

    def goto(self, name: str, pos: int, timeout: int = None) -> str:
        """Move motor `name` to absolute position `pos`."""
        try:
            idx = self.id_dict[name]
            cmd = f"goto {pos} {idx}"
        except KeyError:
            return "Motor not connected"
        return self._send_and_recv(cmd, timeout)

    def home(self, name: str, timeout: int = None) -> str:
        """Home motor `name`."""
        try:
            idx = self.id_dict[name]
            cmd = f"home {idx}"
        except KeyError:
            return "Motor not connected"
        return self._send_and_recv(cmd, timeout)

    def getAPos(self, name: str, timeout: int = None) -> str:
        """Get absolute position of motor `name`."""
        try:
            idx = self.id_dict[name]
            cmd = f"getapos {idx}"
        except KeyError:
            return "Motor not connected"

        resp = self._send_and_recv(cmd, timeout)
        if resp != "Timeout":
            print(f"{name} absolute position: {resp}")
        return resp

    def getPos(self, name: str, timeout: int = None) -> str:
        """Get relative position of motor `name`."""
        try:
            idx = self.id_dict[name]
            cmd = f"getpos {idx}"
        except KeyError:
            return "Motor not connected"
        return self._send_and_recv(cmd, timeout)

    def getAllPos(self, timeout: int = None) -> dict:
        """
        Query every motor’s position in turn, using the same timeout
        for each sub-request.
        """
        positions = {}
        for name in self.id_dict:
            pos = self.getPos(name, timeout)
            try:
                positions[name] = float(pos)
            except (ValueError, TypeError):
                positions[name] = None
        return positions

    def getYaml(self, timeout: int = None) -> str:
        """Retrieve the YAML configuration from the server."""
        return self._send_and_recv("ret_config 1", timeout)

    def close(self):
        """Tear down the ZMQ client cleanly."""
        self.client.close()
        print("Closed connection to motor server.")
