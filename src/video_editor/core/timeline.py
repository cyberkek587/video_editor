import glob
import os
import mpv_ipc # Temporary import for type check or just use the class
from src.video_editor.core.mpv_client import MPVController

class TimelineManager:
    def __init__(self):
        self.files = []
        self.total_duration = 0.0

    def load_folder(self, folder_path, mpv_controller):
        extensions = ('*.MP4', '*.mp4', '*.MOV', '*.mov')
        files_found = []
        for ext in extensions:
            files_found.extend(glob.glob(os.path.join(folder_path, ext)))
        files_found.sort()
        self.files = []
        cumulative_offset = 0.0
        for f in files_found:
            duration = mpv_controller.get_duration_of_file(f)
            if duration:
                self.files.append({"path": f, "duration": duration, "offset": cumulative_offset})
                cumulative_offset += duration
        self.total_duration = cumulative_offset
        return self.files

    def virtual_to_local(self, virtual_time):
        for i, file in enumerate(self.files):
            if file["offset"] <= virtual_time < (file["offset"] + file["duration"]):
                return i, virtual_time - file["offset"]
        if not self.files: return 0, 0
        last = self.files[-1]
        return len(self.files)-1, last["duration"]

    def get_file_at_time(self, virtual_time):
        for i, file in enumerate(self.files):
            if file["offset"] <= virtual_time < (file["offset"] + file["duration"]):
                return i
        return -1
