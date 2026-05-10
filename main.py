import sys
import subprocess
import os
import json
import glob
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
                             QFileDialog, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                             QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QProcess, QTimer, QThread, pyqtSignal
from srt_parser import parse_srt
from mpv_ipc import MPVController
from renderer import VideoRenderer
from timeline_widget import VisualTimeline

class TimelineManager:
    def __init__(self):
        self.files = [] # List of {"path": str, "duration": float, "offset": float}
        self.total_duration = 0.0

    def load_folder(self, folder_path, mpv_controller):
        extensions = ('*.MP4', '*.mp4', '*.MOV', '*.mov')
        files_found = []
        for ext in extensions:
            files_found.extend(glob.glob(os.path.join(folder_path, ext)))
        
        # DJI files are named DJI_YYYYMMDDHHMMSS_... so alphabetical sort = chronological sort
        files_found.sort()
        
        self.files = []
        cumulative_offset = 0.0
        for f in files_found:
            duration = mpv_controller.get_duration_of_file(f)
            if duration:
                self.files.append({
                    "path": f,
                    "duration": duration,
                    "offset": cumulative_offset
                })
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

class RenderThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, files_info, all_segments, save_path):
        super().__init__()
        self.files_info = files_info
        self.all_segments = all_segments
        self.save_path = save_path

    def run(self):
        try:
            renderer = VideoRenderer(self.files_info)
            rendered_files = []
            total = len(self.all_segments)
            
            for i, seg in enumerate(self.all_segments):
                self.progress.emit(int((i / total) * 100), f"Rendering Segment {i+1}/{total} ({seg['type']})...")
                # Use the correct method name: render_virtual_segment
                files = renderer.render_virtual_segment(i, seg['start'], seg['end'], seg['type'])
                if files:
                    rendered_files.extend(files)
            
            if rendered_files:
                self.progress.emit(95, "Assembling final video...")
                if renderer.assemble_final(rendered_files, self.save_path):
                    renderer.cleanup()
                    self.finished.emit(True, "Export Successful!")
                else:
                    self.finished.emit(False, "Assembly failed.")
            else:
                self.finished.emit(False, "No segments to render.")
                
            renderer.cleanup()
        except Exception as e:
            self.finished.emit(False, f"Export error: {str(e)}")

class VideoEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart-Cut Video Editor")
        self.resize(1200, 800)

        self.socket_path = "/tmp/mpv-socket"
        self.mpv_process = None
        self.mpv_controller = MPVController(self.socket_path)
        
        self.timeline = TimelineManager()
        self.current_file_index = -1
        self.current_srt_files = []
        
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
        
        # Main Vertical Layout for the whole window
        main_layout = QVBoxLayout(central_widget)

        # Top Section: Horizontal layout for Navigator and Preview
        top_layout = QHBoxLayout()
        
        # Left Panel: Subtitle Navigator
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.load_folder_btn = QPushButton("Load Folder")
        self.load_folder_btn.clicked.connect(self.open_folder)
        left_layout.addWidget(self.load_folder_btn)

        self.load_srt_btn = QPushButton("Load All Subtitles")
        self.load_srt_btn.clicked.connect(self.load_all_srts)
        left_layout.addWidget(self.load_srt_btn)

        self.subtitle_list = QListWidget()
        self.subtitle_list.itemClicked.connect(self.on_subtitle_clicked)
        left_layout.addWidget(self.subtitle_list)

        # Right Panel: Preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black;")
        right_layout.addWidget(self.video_container)

        top_layout.addWidget(left_panel, 1)
        top_layout.addWidget(right_panel, 3)
        
        # Bottom Panel (Controls)
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        
        # Status Bar / Current Position
        self.status_label = QLabel("Current Position: 00:00:00.00 | Start: -- | End: --")
        bottom_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar)

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

        # Segment Table and Visual Timeline
        self.segment_table = QTableWidget(0, 3)
        self.segment_table.setHorizontalHeaderLabels(["Type", "Start", "End"])
        self.segment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.visual_timeline = VisualTimeline()
        self.visual_timeline.timeClicked.connect(self.seek_virtual_time)
        
        bottom_layout.addWidget(self.visual_timeline)
        bottom_layout.addWidget(self.segment_table)

        # Assemble everything into the main vertical layout
        main_layout.addLayout(top_layout)
        main_layout.addWidget(bottom_panel)

    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Video Folder")
        if folder_path:
            files = self.timeline.load_folder(folder_path, self.mpv_controller)
            if not files:
                QMessageBox.warning(self, "Error", "No compatible video files found in folder.")
                return
            
            self.start_mpv(files[0]["path"])
            self.current_file_index = 0
            self.status_label.setText(f"Loaded {len(files)} files. Total Duration: {self.format_time(self.timeline.total_duration)}")
            self.visual_timeline.set_data(self.calculate_all_segments(), self.timeline.total_duration)

    def load_all_srts(self):
        if not self.timeline.files:
            QMessageBox.warning(self, "Error", "Please load a video folder first.")
            return
            
        folder_path = os.path.dirname(self.timeline.files[0]["path"])
        all_subs = []
        
        for i, file_info in enumerate(self.timeline.files):
            base_name = os.path.splitext(file_info["path"])[0]
            srt_path = base_name + ".srt"
            if os.path.exists(srt_path):
                subs = parse_srt(srt_path)
                offset = file_info["offset"]
                for s in subs:
                    s['start'] += offset
                    s['end'] += offset
                all_subs.extend(subs)
        
        all_subs.sort(key=lambda x: x['start'])
        self.populate_subtitles(all_subs)
        self.current_srt_files = [f + ".srt" for f in [os.path.splitext(fi["path"])[0] for fi in self.timeline.files] if os.path.exists(f + ".srt")]

    def populate_subtitles(self, subs):
        self.subtitle_list.clear()
        for sub in subs:
            timestamp = f"[{self.format_time(sub['start'])}]"
            item = QListWidgetItem(f"{timestamp} {sub['text']}")
            item.setData(Qt.ItemDataRole.UserRole, sub['start'])
            self.subtitle_list.addItem(item)

    def on_subtitle_clicked(self, item):
        v_time = item.data(Qt.ItemDataRole.UserRole)
        self.seek_virtual_time(v_time)

    def seek_virtual_time(self, v_time):
        idx = self.timeline.get_file_at_time(v_time)
        if idx == -1:
            return
        
        if idx != self.current_file_index:
            self.current_file_index = idx
            self.start_mpv(self.timeline.files[idx]["path"])
        
        local_time = v_time - self.timeline.files[idx]["offset"]
        self.mpv_controller.seek(local_time)

    def get_current_virtual_time(self):
        curr_local_time = self.mpv_controller.get_time()
        if curr_local_time is None or self.current_file_index == -1:
            return None
        file_info = self.timeline.files[self.current_file_index]
        return file_info["offset"] + curr_local_time

    def format_time(self, seconds):
        if seconds is None: return "00:00:00.00"
        mins, secs = divmod(max(0, seconds), 60)
        hrs, mins = divmod(mins, 60)
        return f"{int(hrs):02}:{int(mins):02}:{secs:05.2f}"

    def set_start(self):
        v_time = self.get_current_virtual_time()
        if v_time is not None:
            self.temp_start = v_time
            self.update_status()

    def set_end(self):
        v_time = self.get_current_virtual_time()
        if v_time is not None:
            self.temp_end = v_time
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
        
        self.visual_timeline.set_data(all_segments, self.timeline.total_duration)

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
        
        if curr_time is not None:
            # Update visual timeline with current virtual time
            v_time = self.get_current_virtual_time()
            if v_time is not None:
                self.visual_timeline.set_current_time(v_time)

    def export_video(self):
        if not self.timeline.files:
            QMessageBox.warning(self, "Error", "No video loaded")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Exported Video", "output.mp4", "MP4 Video (*.mp4)")
        if not save_path:
            return

        total_duration = self.timeline.total_duration
        if total_duration <= 0:
            QMessageBox.critical(self, "Error", "Could not determine video duration")
            return

        all_segments = self.calculate_all_segments()
        if all_segments:
            last_end = all_segments[-1]['end']
            if last_end < total_duration:
                all_segments.append({"type": "GAP", "start": last_end, "end": total_duration})
        elif total_duration > 0:
            all_segments.append({"type": "GAP", "start": 0, "end": total_duration})

        # Dry Run / Confirmation
        summary = f"Total segments to render: {len(all_segments)}\n"
        keeps = sum(1 for s in all_segments if s['type'] == 'KEEP')
        gaps = sum(1 for s in all_segments if s['type'] == 'GAP')
        summary += f"KEEP: {keeps}, GAP: {gaps}\n\nProceed with export?"
        
        reply = QMessageBox.question(self, "Confirm Export", summary, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.No:
            return

        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.render_thread = RenderThread(self.timeline.files, all_segments, save_path)
        self.render_thread.progress.connect(self.update_render_progress)
        self.render_thread.finished.connect(self.on_render_finished)
        self.render_thread.start()

    def update_render_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.status_label.setText(text)

    def on_render_finished(self, success, message):
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        if success:
            QMessageBox.information(self, "Export", message)
        else:
            QMessageBox.critical(self, "Export Failed", message)

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
        
        # Embed mpv into the video_container widget
        wid = int(self.video_container.winId())
        
        cmd = [
            "mpv",
            f"--wid={wid}",
            f"--input-ipc-server={self.socket_path}",
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
