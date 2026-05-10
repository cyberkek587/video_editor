import sys
import subprocess
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
                             QFileDialog, QLabel, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QProcess, QTimer
from srt_parser import parse_srt
from mpv_ipc import MPVController
from renderer import VideoRenderer

class VideoEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart-Cut Video Editor")
        self.resize(1200, 800)

        self.socket_path = "/tmp/mpv-socket"
        self.mpv_process = None
        self.mpv_controller = MPVController(self.socket_path)
        self.current_video = None
        self.current_srt = None
        
        self.segments = [] # List of {"type": "KEEP", "start": float, "end": float}
        self.temp_start = None
        self.temp_end = None

        self.init_ui()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(500)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel: Subtitle Navigator
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.load_video_btn = QPushButton("Load Video")
        self.load_video_btn.clicked.connect(self.open_video)
        left_layout.addWidget(self.load_video_btn)

        self.load_srt_btn = QPushButton("Load Subtitles")
        self.load_srt_btn.clicked.connect(self.open_srt)
        left_layout.addWidget(self.load_srt_btn)

        self.subtitle_list = QListWidget()
        self.subtitle_list.itemClicked.connect(self.on_subtitle_clicked)
        left_layout.addWidget(self.subtitle_list)

        # Right Panel: Preview (Placeholder for now)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.video_placeholder = QLabel("MPV Preview Window\n(Starts when video is loaded)")
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet("background-color: black; color: white;")
        right_layout.addWidget(self.video_placeholder)

        # Bottom Panel (Controls)
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        
        # Status Bar / Current Position
        self.status_label = QLabel("Current Position: 00:00:00.00 | Start: -- | End: --")
        bottom_layout.addWidget(self.status_label)

        controls_layout = QHBoxLayout()
        self.set_start_btn = QPushButton("Set Start ([)")
        self.set_start_btn.clicked.connect(self.set_start)
        self.set_end_btn = QPushButton("Set End (])")
        self.set_end_btn.clicked.connect(self.set_end)
        self.add_keep_btn = QPushButton("Add Keep Segment (Enter)")
        self.add_keep_btn.clicked.connect(self.add_keep_segment)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_segments)
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_video)
        
        controls_layout.addWidget(self.set_start_btn)
        controls_layout.addWidget(self.set_end_btn)
        controls_layout.addWidget(self.add_keep_btn)
        controls_layout.addWidget(self.clear_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.export_btn)
        bottom_layout.addLayout(controls_layout)

        # Segment Table
        self.segment_table = QTableWidget(0, 3)
        self.segment_table.setHorizontalHeaderLabels(["Type", "Start", "End"])
        self.segment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        bottom_layout.addWidget(self.segment_table)

        # Final Layout Assembly
        content_layout = QVBoxLayout()
        content_layout.addLayout(main_layout)
        content_layout.addWidget(bottom_panel)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)

    def open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.mov *.mkv)")
        if file_path:
            self.current_video = file_path
            self.start_mpv(file_path)

    def open_srt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Subtitles", "", "SRT Files (*.srt)")
        if file_path:
            self.current_srt = file_path
            subs = parse_srt(file_path)
            self.populate_subtitles(subs)
            # Tell mpv to load subtitles too
            if self.mpv_process:
                self.mpv_controller.send_command(["sub-add", file_path])

    def populate_subtitles(self, subs):
        self.subtitle_list.clear()
        for sub in subs:
            timestamp = f"[{self.format_time(sub['start'])}]"
            item = QListWidgetItem(f"{timestamp} {sub['text']}")
            item.setData(Qt.ItemDataRole.UserRole, sub['start'])
            self.subtitle_list.addItem(item)

    def format_time(self, seconds):
        mins, secs = divmod(seconds, 60)
        hrs, mins = divmod(mins, 60)
        return f"{int(hrs):02}:{int(mins):02}:{secs:05.2f}"

    def set_start(self):
        curr_time = self.mpv_controller.get_time()
        if curr_time is not None:
            self.temp_start = curr_time
            self.update_status()

    def set_end(self):
        curr_time = self.mpv_controller.get_time()
        if curr_time is not None:
            self.temp_end = curr_time
            self.update_status()

    def add_keep_segment(self):
        if self.temp_start is not None and self.temp_end is not None:
            start = min(self.temp_start, self.temp_end)
            end = max(self.temp_start, self.temp_end)
            self.segments.append({"type": "KEEP", "start": start, "end": end})
            self.segments.sort(key=lambda x: x['start'])
            self.refresh_segment_table()
            self.temp_start = None
            self.temp_end = None
            self.update_status()

    def clear_segments(self):
        self.segments = []
        self.refresh_segment_table()

    def refresh_segment_table(self):
        self.segment_table.setRowCount(0)
        # We also need to calculate GAPs for the table display
        all_segments = self.calculate_all_segments()
        self.segment_table.setRowCount(len(all_segments))
        for i, seg in enumerate(all_segments):
            self.segment_table.setItem(i, 0, QTableWidgetItem(seg['type']))
            self.segment_table.setItem(i, 1, QTableWidgetItem(self.format_time(seg['start'])))
            self.segment_table.setItem(i, 2, QTableWidgetItem(self.format_time(seg['end'])))
            if seg['type'] == "GAP":
                for j in range(3):
                    self.segment_table.item(i, j).setForeground(Qt.GlobalColor.gray)

    def calculate_all_segments(self):
        if not self.segments:
            return []
        
        # Assuming video starts at 0
        all_segs = []
        last_end = 0.0
        
        for keep in self.segments:
            if keep['start'] > last_end:
                all_segs.append({"type": "GAP", "start": last_end, "end": keep['start']})
            all_segs.append(keep)
            last_end = keep['end']
        
        # We don't necessarily know the total duration yet, 
        # but for the purpose of the list, this is enough.
        return all_segs

    def update_status(self):
        curr_time = self.mpv_controller.get_time()
        curr_str = self.format_time(curr_time) if curr_time is not None else "00:00:00.00"
        start_str = self.format_time(self.temp_start) if self.temp_start is not None else "--"
        end_str = self.format_time(self.temp_end) if self.temp_end is not None else "--"
        self.status_label.setText(f"Current Position: {curr_str} | Start: {start_str} | End: {end_str}")

    def export_video(self):
        if not self.current_video:
            print("No video loaded")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Exported Video", "output.mp4", "MP4 Video (*.mp4)")
        if not save_path:
            return

        # Calculate total duration to close the final gap
        total_duration = self.mpv_controller.get_duration()
        if total_duration is None:
            print("Could not determine video duration")
            return

        # Get all segments
        all_segments = self.calculate_all_segments()
        
        # Add final gap if the last segment doesn't reach the end
        if all_segments:
            last_end = all_segments[-1]['end']
            if last_end < total_duration:
                all_segments.append({"type": "GAP", "start": last_end, "end": total_duration})
        elif total_duration > 0:
            # No KEEP segments, the whole thing is one GAP
            all_segments.append({"type": "GAP", "start": 0, "end": total_duration})

        self.export_btn.setEnabled(False)
        self.export_btn.setText("Rendering...")
        QApplication.processEvents()

        try:
            renderer = VideoRenderer(self.current_video)
            rendered_files = []
            
            for i, seg in enumerate(all_segments):
                self.status_label.setText(f"Rendering Segment {i+1}/{len(all_segments)} ({seg['type']})...")
                QApplication.processEvents()
                
                file = renderer.render_segment(i, seg['start'], seg['end'], seg['type'])
                if file:
                    rendered_files.append(file)

            if rendered_files:
                self.status_label.setText("Assembling final video...")
                QApplication.processEvents()
                if renderer.assemble_final(rendered_files, save_path):
                    self.status_label.setText("Export Successful!")
                else:
                    self.status_label.setText("Assembly failed.")
            else:
                self.status_label.setText("No segments to render.")

            renderer.cleanup()
        except Exception as e:
            print(f"Export error: {e}")
            self.status_label.setText(f"Error: {e}")
        finally:
            self.export_btn.setEnabled(True)
            self.export_btn.setText("Export")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_BracketLeft:
            self.set_start()
        elif event.key() == Qt.Key.Key_BracketRight:
            self.set_end()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.add_keep_segment()
        super().keyPressEvent(event)

    def start_mpv(self, video_path):
        if self.mpv_process:
            self.mpv_process.terminate()
        
        # In a real app, we'd try to embed this using WID.
        # For now, we'll just launch it externally with IPC enabled.
        # Note: On Wayland, embedding is tricky.
        cmd = [
            "mpv",
            f"--input-ipc-server={self.socket_path}",
            "--ontop", # Helpful for external window
            video_path
        ]
        self.mpv_process = QProcess(self)
        self.mpv_process.start("mpv", cmd[1:])

    def closeEvent(self, event):
        if self.mpv_process:
            self.mpv_process.terminate()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoEditorApp()
    window.show()
    sys.exit(app.exec())
