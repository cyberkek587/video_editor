import sys
import subprocess
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
                             QFileDialog, QLabel)
from PyQt6.QtCore import Qt, QProcess
from srt_parser import parse_srt
from mpv_ipc import MPVController

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

        self.init_ui()

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
        bottom_layout = QHBoxLayout(bottom_panel)
        self.set_start_btn = QPushButton("Set Start")
        self.set_end_btn = QPushButton("Set End")
        self.add_keep_btn = QPushButton("Add Keep Segment")
        self.export_btn = QPushButton("Export")
        
        bottom_layout.addWidget(self.set_start_btn)
        bottom_layout.addWidget(self.set_end_btn)
        bottom_layout.addWidget(self.add_keep_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.export_btn)

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

    def on_subtitle_clicked(self, item):
        start_time = item.data(Qt.ItemDataRole.UserRole)
        self.mpv_controller.seek(start_time)

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
