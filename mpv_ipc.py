import socket
import json
import os

import time

class MPVController:
    def __init__(self, socket_path='/tmp/mpv-socket'):
        self.socket_path = socket_path

    def send_command(self, command):
        # Retry a few times in case mpv is still starting
        for _ in range(5):
            if os.path.exists(self.socket_path):
                break
            time.sleep(0.2)
        else:
            print(f"Socket {self.socket_path} not found.")
            return None

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(self.socket_path)
                msg = json.dumps({"command": command}) + '\n'
                client.sendall(msg.encode('utf-8'))
                
                # We might want to read the response if needed
                # For basic seeking, we might not care immediately
                # response = client.recv(4096)
                # return json.loads(response.decode('utf-8'))
                return True
        except Exception as e:
            print(f"Error communicating with mpv: {e}")
            return None

    def seek(self, seconds):
        return self.send_command(["set_property", "time-pos", seconds])

    def pause(self):
        return self.send_command(["set_property", "pause", True])

    def resume(self):
        return self.send_command(["set_property", "pause", False])

    def get_property(self, property_name):
        if not os.path.exists(self.socket_path):
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(self.socket_path)
                msg = json.dumps({"command": ["get_property", property_name]}) + '\n'
                client.sendall(msg.encode('utf-8'))
                response = client.recv(4096)
                data = json.loads(response.decode('utf-8'))
                return data.get('data')
        except Exception as e:
            print(f"Error getting property from mpv: {e}")
            return None

    def get_time(self):
        return self.get_property("time-pos")

    def get_duration(self):
        return self.get_property("duration")
