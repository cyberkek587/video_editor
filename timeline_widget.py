from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

class VisualTimeline(QWidget):
    timeClicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments = []  # List of {"type": "KEEP"|"GAP", "start": float, "end": float}
        self.files_info = [] # List of {"path": str, "duration": float, "offset": float}
        self.total_duration = 0.0
        self.current_time = 0.0
        self.setMinimumHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_data(self, segments, total_duration, files_info=None):
        self.segments = segments
        self.total_duration = total_duration
        self.files_info = files_info if files_info else []
        self.update()

    def set_current_time(self, time):
        self.current_time = time
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        if self.total_duration <= 0:
            painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, "No video loaded")
            return

        # Background
        painter.setBrush(QBrush(QColor(40, 40, 40)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, width, height)

        # Draw segments
        for seg in self.segments:
            start_x = (seg['start'] / self.total_duration) * width
            end_x = (seg['end'] / self.total_duration) * width
            
            if seg['type'] == "KEEP":
                painter.setBrush(QBrush(QColor(46, 204, 113))) # Green
            else:
                painter.setBrush(QBrush(QColor(149, 165, 166))) # Grey
            
            painter.drawRect(int(start_x), 10, int(end_x - start_x), height - 20)

        # Draw file boundaries
        painter.setPen(QPen(QColor(200, 200, 200, 150), 1, Qt.PenStyle.DashLine))
        for i, file in enumerate(self.files_info):
            # Draw line at the end of each file (except the last one)
            if i < len(self.files_info) - 1:
                boundary_x = ((file["offset"] + file["duration"]) / self.total_duration) * width
                painter.drawLine(int(boundary_x), 0, int(boundary_x), height)

        # Current time indicator
        curr_x = (self.current_time / self.total_duration) * width
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawLine(int(curr_x), 0, int(curr_x), height)

    def mousePressEvent(self, event):
        if self.total_duration <= 0:
            return
            
        click_x = event.position().x()
        clicked_time = (click_x / self.width()) * self.total_duration
        self.timeClicked.emit(clicked_time)
