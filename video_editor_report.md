# Smart-Cut Video Editor Progress Report

## Project Status: Stable Beta (Refactored)

The project has transitioned from a single-file MVP to a professional, multi-file virtual editing tool. The architecture has been refactored into a modular package structure (`src/`) for better maintainability.

## Completed Features

### 1. Core Engine & Architecture
- [x] **Multi-File Virtual Timeline**: Supports loading folders of DJI-style videos, sorting them chronologically, and treating them as one continuous stream.
- [x] **Lossless Rendering Pipeline**: Implemented a high-performance "Keep" strategy using FFmpeg stream copying (`-c copy`).
- [x] **Keyframe-Aware Cutting**: Implemented "Snapping" to the nearest I-frame (Keyframe) to prevent corrupted output files and playback freezes.
- [x] **Parallel Processing**: Integrated `ThreadPoolExecutor` to utilize multiple CPU cores during the rendering of segments, significantly increasing export speed.
- [x] **Project Persistence**: Added the ability to save and load segment configurations via `.txt` (JSON) files.

### 2. UI & User Experience
- [x] **Speech-Driven Navigation**: Subtitle-based jumping using `mpv` IPC sockets.
- [x] **Dynamic Layout**: 
    - Implemented `QSplitter` for adjustable panel widths.
    - Added "Hide Preview" mode to maximize workspace for subtitle navigation.
- [x] **Visual Timeline**: A graphical representation of KEEP/GAP zones with a real-time playback indicator.
- [x] **Auto-Submit Workflow**: "Set End" marker automatically adds the segment to the list, streamlining the editing process.
- [x] **Overlap Management**: Automatic merging of overlapping or adjacent KEEP segments.

### 3. Subtitle Integration
- [x] **Global SRT Mapping**: Load all subtitles in a folder and offset them to match the virtual timeline.
- [x] **Auto-Highlighting**: The subtitle list now automatically scrolls and highlights the current line being spoken in the video.
- [x] **Export Sync**: Automatic generation of a new `.srt` file for exported videos, with timestamps re-mapped to the new, shorter timeline.

## Technical Specifications (Current)
- **Video Codec**: H.265/HEVC (Source-matched).
- **Audio Codec**: AAC 192k Stereo.
- **Timeline Base**: 30000/1001 FPS (Standard NTSC).
- **Export Strategy**: Pure Lossless (KEEP segments only) to guarantee stability.

## Pending & Future Goals

### Short-Term (Polish)
- [ ] **Smart Cut Implementation**: Return to the "Smart Cut" approach (re-encoding only the gap between the desired cut and the nearest keyframe) to allow frame-accurate cuts without sacrificing the rest of the clip's quality.
- [ ] **Audio Transitions**: Implement simple cross-fades or fades between concatenated segments to avoid "pops" in the audio.
- [ ] **Visual Timeline Editing**: Allow users to drag and resize KEEP/GAP zones directly on the graphical bar.

### Long-Term (Advanced)
- [ ] **Proxy Previews**: Low-resolution proxy rendering for GAP segments to preview timelapse speed before final export.
- [ ] **Batch Processing**: Queue multiple projects for overnight rendering.
- [ ] **Audio Track Selection**: Support for choosing specific audio channels from multi-track recordings.

## Developer Notes for Resume
- **Entry Point**: `main.py`
- **Logic Core**: `src/video_editor/core/`
- **UI Components**: `src/video_editor/ui/`
- **Current Dependencies**: `PyQt6`, `pysrt`, `mpv`, `ffmpeg`
