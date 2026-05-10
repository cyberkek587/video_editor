import socket
import json
import os
import subprocess
import time

class MPVController:
    def __init__(self, socket_path='/tmp/mpv-socket'):
        self.socket_path = socket_path

    def send_command(self, command):
        for _ in range(5):
            if os.path.exists(self.socket_path):
                break
            time.sleep(0.2)
        else:
            return None

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(self.socket_path)
                msg = json.dumps({"command": command}) + '\n'
                client.sendall(msg.encode('utf-8'))
                return True
        except (ConnectionRefusedError, socket.error):
            return None
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
                response = client.recv(4096).decode('utf-8')
                for line in response.splitlines():
                    if line.strip():
                        data = json.loads(line)
                        return data.get('data')
                return None
        except (ConnectionRefusedError, socket.error):
            return None
        except Exception as e:
            print(f"Error getting property from mpv: {e}")
            return None

    def get_time(self):
        return self.get_property("time-pos")

    def get_duration(self):
        return self.get_property("duration")

    def get_duration_of_file(self, file_path):
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Error getting duration for {file_path}: {e}")
            return None
