import subprocess
import os
import math

class VideoRenderer:
    def __init__(self, files_info, output_dir="temp_segments"):
        """
        files_info: List of {"path": str, "duration": float, "offset": float}
        """
        self.files_info = files_info
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def render_virtual_segment(self, virtual_index, v_start, v_end, segment_type):
        """
        Splits a virtual segment across multiple files and renders each part.
        Returns a list of resulting file paths.
        """
        results = []
        
        for i, file in enumerate(self.files_info):
            f_start = file["offset"]
            f_end = file["offset"] + file["duration"]
            
            # Check if this file overlaps with the virtual segment
            overlap_start = max(v_start, f_start)
            overlap_end = min(v_end, f_end)
            
            if overlap_start < overlap_end:
                # Calculate local times within this specific file
                local_start = overlap_start - f_start
                local_end = overlap_end - f_start
                
                output_file = os.path.join(self.output_dir, f"seg_{virtual_index:04d}_{i:03d}_{segment_type}.mp4")
                
                if segment_type == "KEEP":
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(local_start),
                        "-to", str(local_end),
                        "-i", file["path"],
                        "-c", "copy",
                        output_file
                    ]
                else: # GAP
                    # Relative speed factor based on the total virtual duration of this GAP segment
                    v_duration = v_end - v_start
                    speed_factor = max(1, math.floor(v_duration / 10.0))
                    filter_complex = f"select='not(mod(n,{speed_factor}))',setpts={1.0/speed_factor}*PTS"
                    
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(local_start),
                        "-to", str(local_end),
                        "-i", file["path"],
                        "-vf", filter_complex,
                        "-an", 
                        output_file
                    ]
                
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    results.append(output_file)
                except subprocess.CalledProcessError as e:
                    print(f"Error rendering part {i} of segment {virtual_index}: {e.stderr.decode()}")
        
        return results

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
