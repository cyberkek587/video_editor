import subprocess
import os
import math

class VideoRenderer:
    def __init__(self, files_info, output_dir="temp_segments"):
        self.files_info = files_info
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_codec(self, file_path):
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            codec = result.stdout.strip()
            if "hevc" in codec:
                return "libx265"
            return "libx264"
        except Exception:
            return "libx264"

    def get_nearest_keyframe(self, file_path, timestamp):
        """Finds the nearest keyframe at or before the given timestamp."""
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "frame=pkt_pts_time",
            "-read_intervals", f"0%{timestamp}",
            "-of", "compact=p=0:nk=1",
            file_path
        ]
        try:
            # Added timeout to prevent hanging on corrupted files
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            timestamps = result.stdout.strip().splitlines()
            return float(timestamps[-1]) if timestamps else 0.0
        except Exception as e:
            print(f"Error finding keyframe: {e}")
            return timestamp

    def render_virtual_segment(self, virtual_index, v_start, v_end, segment_type):
        results = []
        for i, file in enumerate(self.files_info):
            f_start = file["offset"]
            f_end = file["offset"] + file["duration"]
            overlap_start = max(v_start, f_start)
            overlap_end = min(v_end, f_end)
            if overlap_start < overlap_end:
                local_start = overlap_start - f_start
                local_end = overlap_end - f_start
                output_file = os.path.join(self.output_dir, f"seg_{virtual_index:04d}_{i:03d}_{segment_type}.mp4")
                
                actual_start = local_start
                if segment_type == "KEEP":
                    actual_start = self.get_nearest_keyframe(file["path"], local_start)
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(actual_start),
                        "-i", file["path"],
                        "-to", str(local_end - actual_start),
                        "-c", "copy",
                        "-avoid_negative_ts", "make_zero",
                        "-map", "0:v", "-map", "0:a",
                        output_file
                    ]
                else: # GAP
                    v_duration = v_end - v_start
                    speed_factor = max(1, math.floor(v_duration / 10.0))
                    fps = "30000/1001"
                    filter_complex = f"select='not(mod(n,{speed_factor}))',setpts=N/({fps}*TB),fps={fps}"
                    codec = self.get_codec(file["path"])
                    cmd = [
                        "ffmpeg", "-y", "-ss", str(local_start), "-to", str(local_end), "-i", file["path"],
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-vf", filter_complex, "-map", "0:v", "-map", "1:a", "-c:v", codec,
                        "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p", "-r", fps,
                        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-movflags", "+faststart", "-shortest", output_file
                    ]
                try:
                    # Added timeout to prevent hanging on a single segment
                    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
                    results.append((output_file, actual_start))
                except subprocess.CalledProcessError as e:
                    print(f"Error rendering part {i}: {e.stderr.decode()}")
                except subprocess.TimeoutExpired:
                    print(f"Timeout rendering part {i}")
        return results

    def assemble_final(self, segment_files, final_output):
        list_file = os.path.join(self.output_dir, "list.txt")
        with open(list_file, "w") as f:
            for file in segment_files:
                # We expect tuples (path, actual_start) now
                path = file[0] if isinstance(file, tuple) else file
                f.write(f"file '{os.path.abspath(path)}'\n")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-map", "0:v", "-map", "0:a", "-c", "copy", final_output]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error assembling: {e.stderr.decode()}")
            return False

    def cleanup(self):
        import shutil
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
