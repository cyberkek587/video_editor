import subprocess
import os
import math

class VideoRenderer:
    def __init__(self, input_file, output_dir="temp_segments"):
        self.input_file = input_file
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def render_segment(self, index, start, end, segment_type):
        output_file = os.path.join(self.output_dir, f"seg_{index:04d}_{segment_type}.mp4")
        
        if segment_type == "KEEP":
            # Lossless stream copy
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", self.input_file,
                "-c", "copy",
                output_file
            ]
        else: # GAP
            # Optimized Timelapse: target ~10 seconds duration
            duration = end - start
            if duration <= 0:
                return None
                
            speed_factor = max(1, math.floor(duration / 10.0))
            
            # select filter drops frames. setpts adjusts timestamps.
            # -an removes audio for timelapses to avoid glitches
            filter_complex = f"select='not(mod(n,{speed_factor}))',setpts={1.0/speed_factor}*PTS"
            
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", self.input_file,
                "-vf", filter_complex,
                "-an", 
                output_file
            ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"Error rendering segment {index}: {e.stderr.decode()}")
            return None

    def assemble_final(self, segment_files, final_output):
        list_file = os.path.join(self.output_dir, "list.txt")
        with open(list_file, "w") as f:
            for file in segment_files:
                # ffmpeg concat requires absolute paths or relative to list file
                # and 'file ' prefix
                abs_path = os.path.abspath(file)
                f.write(f"file '{abs_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            final_output
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error assembling final video: {e.stderr.decode()}")
            return False

    def cleanup(self):
        import shutil
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
