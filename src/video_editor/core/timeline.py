import glob
import os
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

    def get_nearest_keyframe(self, file_path, timestamp):
        """
        Finds the nearest keyframe at or before the given timestamp.
        """
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "frame=pkt_pts_time",
            "-read_intervals", f"0%{timestamp}",
            "-of", "compact=p=0:nk=1",
            file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            timestamps = result.stdout.strip().splitlines()
            if not timestamps:
                return 0.0
            return float(timestamps[-1])
        except Exception as e:
            print(f"Error finding keyframe: {e}")
            return timestamp

    def get_file_at_time(self, virtual_time):
        for i, file in enumerate(self.files):
            if file["offset"] <= virtual_time < (file["offset"] + file["duration"]):
                return i
        return -1
