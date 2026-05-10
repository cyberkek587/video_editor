import sys
import os
import json
import glob
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
                             QFileDialog, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
                             QProgressBar, QMessageBox, QSplitter, QCheckBox)
from PyQt6.QtCore import Qt, QProcess, QTimer, QThread, pyqtSignal

from src.video_editor.core.srt_utils import parse_srt
from src.video_editor.core.mpv_client import MPVController
from src.video_editor.core.renderer import VideoRenderer
from src.video_editor.core.timeline import TimelineManager
from src.video_editor.ui.widgets import VisualTimeline
import json as json_lib
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            
            with ThreadPoolExecutor() as executor:
                future_to_seg = {
                    executor.submit(renderer.render_virtual_segment, i, seg['start'], seg['end'], seg['type']): i 
                    for i, seg in enumerate(self.all_segments)
                }
                
                completed_count = 0
                results_map = {}

                for future in as_completed(future_to_seg):
                    seg_idx = future_to_seg[future]
                    files = future.result()
                    if files:
                        results_map[seg_idx] = files
                    
                    completed_count += 1
                    seg_type = self.all_segments[seg_idx]['type']
                    self.progress.emit(int((completed_count / total) * 100), f"Rendering Segment {seg_idx+1}/{total} ({seg_type})...")

            for i in range(total):
                if i in results_map:
                    rendered_files.extend(results_map[i])
            
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
        
        self.segments = [] 
        self.temp_start = None
        self.temp_end = None

        self.init_ui()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(500)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        self.load_folder_btn = QPushButton("Load Folder")
        self.load_folder_btn.clicked.connect(self.open_folder)
        left_layout.addWidget(self.load_folder_btn)

        self.load_srt_btn = QPushButton("Load All Subtitles")
        self.load_srt_btn.clicked.connect(self.load_all_srts)
        left_layout.addWidget(self.load_srt_btn)

        self.subtitle_list = QListWidget()
        self.subtitle_list.itemClicked.connect(self.on_subtitle_clicked)
        left_layout.addWidget(self.subtitle_list)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: black;")
        right_layout.addWidget(self.video_container)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
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
        self.save_segments_btn = QPushButton("Save Project")
        self.save_segments_btn.clicked.connect(self.save_segments_to_file)
        self.load_segments_btn = QPushButton("Load Project")
        self.load_segments_btn.clicked.connect(self.load_segments_from_file)
        
        self.hide_preview_cb = QCheckBox("Hide Preview")
        self.hide_preview_cb.setChecked(True)
        self.hide_preview_cb.toggled.connect(self.toggle_preview)
        
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_video)
        
        controls_layout.addWidget(self.set_start_btn)
        controls_layout.addWidget(self.set_end_btn)
        controls_layout.addWidget(self.add_keep_btn)
        controls_layout.addWidget(self.clear_btn)
        controls_layout.addWidget(self.save_segments_btn)
        controls_layout.addWidget(self.load_segments_btn)
        controls_layout.addWidget(self.hide_preview_cb)
        controls_layout.addStretch()
        controls_layout.addWidget(self.export_btn)
        bottom_layout.addLayout(controls_layout)

        self.segment_table = QTableWidget(0, 3)
        self.segment_table.setHorizontalHeaderLabels(["Type", "Start", "End"])
        self.segment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.segment_table.itemDoubleClicked.connect(self.remove_segment)
        
        self.visual_timeline = VisualTimeline()
        self.visual_timeline.timeClicked.connect(self.seek_virtual_time)
        
        bottom_layout.addWidget(self.visual_timeline)
        bottom_layout.addWidget(self.segment_table)

        main_layout.addWidget(self.splitter)
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
            self.visual_timeline.set_data(self.calculate_all_segments(), self.timeline.total_duration, self.timeline.files)

    def load_all_srts(self):
        if not self.timeline.files:
            QMessageBox.warning(self, "Error", "Please load a video folder first.")
            return
        folder_path = os.path.dirname(self.timeline.files[0]["path"])
        grouped_subs = []
        for i, file_info in enumerate(self.timeline.files):
            base_name = os.path.splitext(file_info["path"])[0]
            srt_path = base_name + ".srt"
            file_name = os.path.basename(file_info["path"])
            if os.path.exists(srt_path):
                subs = parse_srt(srt_path)
                offset = file_info["offset"]
                for s in subs:
                    s['start'] += offset
                    s['end'] += offset
                subs.sort(key=lambda x: x['start'])
                grouped_subs.append({"file_name": file_name, "subs": subs})
        self.populate_subtitles(grouped_subs)
        self.current_srt_files = [f + ".srt" for f in [os.path.splitext(fi["path"])[0] for fi in self.timeline.files] if os.path.exists(f + ".srt")]

    def populate_subtitles(self, grouped_subs):
        self.subtitle_list.clear()
        for group in grouped_subs:
            header = QListWidgetItem(f"#{group['file_name']}")
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            self.subtitle_list.addItem(header)
            for sub in group['subs']:
                timestamp = f"[{self.format_time(sub['start'])}]"
                item = QListWidgetItem(f"{timestamp} {sub['text']}")
                item.setData(Qt.ItemDataRole.UserRole, {'start': sub['start'], 'end': sub['end']})
                self.subtitle_list.addItem(item)

    def on_subtitle_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict) and 'start' in data:
            self.seek_virtual_time(data['start'])

    def seek_virtual_time(self, v_time):
        idx = self.timeline.get_file_at_time(v_time)
        if idx == -1: return
        if idx != self.current_file_index:
            self.current_file_index = idx
            self.start_mpv(self.timeline.files[idx]["path"])
        local_time = v_time - self.timeline.files[idx]["offset"]
        self.mpv_controller.seek(local_time)

    def get_current_virtual_time(self):
        curr_local_time = self.mpv_controller.get_time()
        if curr_local_time is None or self.current_file_index == -1: return None
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
            if self.temp_start is not None:
                self.add_keep_segment()
            else:
                self.update_status()

    def add_keep_segment(self):
        if self.temp_start is not None and self.temp_end is not None:
            start = min(self.temp_start, self.temp_end)
            end = max(self.temp_start, self.temp_end)
            self.segments.append({"type": "KEEP", "start": start, "end": end})
            self.segments.sort(key=lambda x: x['start'])
            if len(self.segments) > 1:
                merged = []
                current_seg = self.segments[0].copy()
                for next_seg in self.segments[1:]:
                    if next_seg['start'] <= current_seg['end']:
                        current_seg['end'] = max(current_seg['end'], next_seg['end'])
                    else:
                        merged.append(current_seg)
                        current_seg = next_seg.copy()
                merged.append(current_seg)
                self.segments = merged
            self.refresh_segment_table()
            self.temp_start = None
            self.temp_end = None
            self.update_status()

    def clear_segments(self):
        self.segments = []
        self.refresh_segment_table()
        self.save_segments_to_file()

    def load_segments_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Segments", "", "Segments Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "r") as f:
                    data = json_lib.load(f)
                    self.segments = data
                    self.segments.sort(key=lambda x: x['start'])
                    self.refresh_segment_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load segments: {e}")

    def save_segments_to_file(self):
        if not self.segments: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Segments", "segments.txt", "Segments Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w") as f:
                    json_lib.dump(self.segments, f)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save segments: {e}")

    def remove_segment(self, item):
        row = item.row()
        all_segs = self.calculate_all_segments()
        seg_to_remove = all_segs[row]
        if seg_to_remove['type'] == "KEEP":
            for i, s in enumerate(self.segments):
                if s['start'] == seg_to_remove['start'] and s['end'] == seg_to_remove['end']:
                    self.segments.pop(i)
                    break
        else:
            QMessageBox.information(self, "Info", "Gaps are automatic. To remove a gap, adjust the adjacent Keep segments.")
            return
        self.refresh_segment_table()

    def refresh_segment_table(self):
        self.segment_table.setRowCount(0)
        all_segments = self.calculate_all_segments()
        self.segment_table.setRowCount(len(all_segments))
        for i, seg in enumerate(all_segments):
            self.segment_table.setItem(i, 0, QTableWidgetItem(seg['type']))
            self.segment_table.setItem(i, 1, QTableWidgetItem(self.format_time(seg['start'])))
            self.segment_table.setItem(i, 2, QTableWidgetItem(self.format_time(seg['end'])))
            if seg['type'] == "GAP":
                for j in range(3):
                    self.segment_table.item(i, j).setForeground(Qt.GlobalColor.gray)
        self.visual_timeline.set_data(all_segments, self.timeline.total_duration, self.timeline.files)

    def calculate_all_segments(self):
        if not self.segments: return []
        all_segs = []
        last_end = 0.0
        for keep in self.segments:
            if keep['start'] > last_end:
                all_segs.append({"type": "GAP", "start": last_end, "end": keep['start']})
            all_segs.append(keep)
            last_end = keep['end']
        return all_segs

    def update_status(self):
        curr_time = self.mpv_controller.get_time()
        curr_str = self.format_time(curr_time) if curr_time is not None else "00:00:00.00"
        start_str = self.format_time(self.temp_start) if self.temp_start is not None else "--"
        end_str = self.format_time(self.temp_end) if self.temp_end is not None else "--"
        self.status_label.setText(f"Current Position: {curr_str} | Start: {start_str} | End: {end_str}")
        if curr_time is not None:
            v_time = self.get_current_virtual_time()
            if v_time is not None:
                self.visual_timeline.set_current_time(v_time)
                self.highlight_current_subtitle(v_time)

    def highlight_current_subtitle(self, v_time):
        for i in range(self.subtitle_list.count()):
            item = self.subtitle_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and 'start' in data:
                if data['start'] <= v_time < data['end']:
                    self.subtitle_list.setCurrentItem(item)
                    self.subtitle_list.scrollToItem(item)
                    break

    def export_video(self):
        if not self.timeline.files:
            QMessageBox.warning(self, "Error", "No video loaded")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Exported Video", "output.mp4", "MP4 Video (*.mp4)")
        if not save_path: return
        keep_segments = [s for s in self.segments]
        if not keep_segments:
            QMessageBox.warning(self, "Error", "No keep segments defined.")
            return
        summary = f"Total segments to render: {len(keep_segments)}\nKEEP: {len(keep_segments)}, GAP: 0 (Removed)\n\nProceed with export?"
        reply = QMessageBox.question(self, "Confirm Export", summary, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.render_thread = RenderThread(self.timeline.files, keep_segments, save_path)
        self.render_thread.progress.connect(self.update_render_progress)
        self.render_thread.finished.connect(lambda success, msg: self.on_render_finished(success, msg, save_path))
        self.render_thread.start()

    def update_render_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.status_label.setText(text)

    def on_render_finished(self, success, message, save_path=None):
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        if success:
            self.generate_output_srt(save_path)
            QMessageBox.information(self, "Export", message)
        else:
            QMessageBox.critical(self, "Export Failed", message)

    def generate_output_srt(self, video_path):
        srt_output_path = os.path.splitext(video_path)[0] + ".srt"
        all_subs = []
        for file_info in self.timeline.files:
            base_name = os.path.splitext(file_info["path"])[0]
            srt_path = base_name + ".srt"
            if os.path.exists(srt_path):
                subs = parse_srt(srt_path)
                offset = file_info["offset"]
                for s in subs:
                    # s is already a dict from parse_srt: {'start': float, 'end': float, 'text': str}
                    all_subs.append({
                        'start': s['start'] + offset, 
                        'end': s['end'] + offset, 
                        'text': s['text']
                    })
        all_subs.sort(key=lambda x: x['start'])
        new_subs = []
        current_virtual_offset = 0.0
        for keep in self.segments:
            k_start, k_end = keep['start'], keep['end']
            for sub in all_subs:
                if sub['start'] < k_end and sub['end'] > k_start:
                    actual_start = max(sub['start'], k_start)
                    actual_end = min(sub['end'], k_end)
                    new_subs.append({
                        'start': current_virtual_offset + (actual_start - k_start), 
                        'end': current_virtual_offset + (actual_end - k_start), 
                        'text': sub['text']
                    })
            current_virtual_offset += (k_end - k_start)
        def format_srt_time(seconds):
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hrs:02}:{mins:02}:{secs:05.2f}".replace('.', ',')
        try:
            with open(srt_output_path, "w", encoding="utf-8") as f:
                for i, sub in enumerate(new_subs, 1):
                    f.write(f"{i}\n{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n{sub['text']}\n\n")
        except Exception as e:
            print(f"Error writing SRT file: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_BracketLeft: self.set_start()
        elif event.key() == Qt.Key.Key_BracketRight: self.set_end()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self.add_keep_segment()
        super().keyPressEvent(event)

    def start_mpv(self, video_path):
        if self.mpv_process: self.mpv_process.terminate()
        wid = int(self.video_container.winId())
        cmd = ["mpv", f"--wid={wid}", f"--input-ipc-server={self.socket_path}", "--keep-open", video_path]
        self.mpv_process = QProcess(self)
        self.mpv_process.start("mpv", cmd[1:])

    def toggle_preview(self, hide):
        self.right_panel.setVisible(not hide)

    def closeEvent(self, event):
        if self.mpv_process: self.mpv_process.terminate()
        if os.path.exists(self.socket_path): os.remove(self.socket_path)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoEditorApp()
    window.show()
    sys.exit(app.exec())
