# Smart-Cut Video Editor

A high-performance video editing tool designed for long-form recordings where the primary markers of interest are spoken words. The application uses AI-generated subtitles (SRT) as a navigation map to quickly identify segments to keep and segments to compress into timelapses.

## Key Features

- Multi-File Virtual Timeline: Treat a folder of video files as a single continuous timeline.
- Lossless "Keep" Zones: Maintains original quality for selected segments using stream copying.
- Optimized "Gap" Timelapses: Automatically converts intervals between keep zones into fast timelapses with synchronized audio.
- Speech-Driven Navigation: Integrated subtitle list allowing users to jump to specific timestamps instantly.
- H.265/HEVC Optimization: Specifically tuned for DJI-style high-efficiency video recordings.
- Project Persistence: Save and load segment configurations to text files.
- Dynamic UI: Resizable panels and optional preview hiding for maximum workspace efficiency.

## Tech Stack

- Language: Python 3.x
- GUI Framework: PyQt6
- Video Preview Engine: mpv (via JSON-RPC/IPC)
- Processing Engine: ffmpeg

## Installation

1. Install System Dependencies:
   - mpv
   - ffmpeg

2. Set up Environment:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt # if applicable, otherwise pysrt and PyQt6
   ```

3. Run Application:
   ```bash
   python main.py
   ```

## Usage

1. Load Folder: Select a folder containing video files (.mp4, .mov).
2. Load Subtitles: Load corresponding .srt files to populate the navigator.
3. Mark Segments:
   - Press [ to set the start of a keep zone.
   - Press ] to set the end (segment is automatically submitted).
4. Export: Click Export to render the final merged video.
