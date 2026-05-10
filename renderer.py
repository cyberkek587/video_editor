import subprocess
import os
import math

class VideoRenderer:
    def get_codec(self, file_path):
        """Detects if the file is h264 or h265."""
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
            return "libx264" # Fallback

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
                    
                    # Match the codec of the original file
                    codec = self.get_codec(file["path"])
                    
                    # Use optimized settings based on user's converter config
                    # We use 'ultrafast' preset for GAP segments to keep rendering speed high
                    preset = "ultrafast" if codec == "libx265" else "ultrafast"
                    
                    # Create a silent audio track that matches the resulting video length
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(local_start),
                        "-to", str(local_end),
                        "-i", file["path"],
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-vf", filter_complex,
                        "-map", "0:v",
                        "-map", "1:a",
                        "-c:v", codec,
                        "-preset", preset,
                        "-crf", "28",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-ac", "2",
                        "-movflags", "+faststart",
                        "-shortest",
                        output_file
                    ]
                
                try:
                    # Use a slightly higher probe size for the rendering if needed
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
