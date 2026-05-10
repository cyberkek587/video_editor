# Smart-Cut Video Editor Documentation

## 1. Overview
The **Smart-Cut Video Editor** is a high-performance tool designed for long-form 4K recordings (e.g., DJI drones/cameras). It enables a speech-driven editing workflow where AI-generated subtitles (SRT) act as a navigation map to quickly identify and mark "KEEP" segments of original quality, while automatically managing the "GAPs" between them.

## 2. Core Architecture

### 2.1 Virtual Timeline (`TimelineManager`)
Instead of editing a single file, the app creates a **Virtual Timeline**. It loads all video files in a folder, sorts them, and assigns each a global offset. 
- **Virtual Time**: A continuous timestamp across multiple files.
- **Local Time**: The timestamp relative to the start of a specific file.

### 2.2 Preview Engine (`MPVController`)
The application uses `mpv` as its rendering engine, communicating via a Unix IPC socket. This allows the Python GUI to:
- Seek to precise timestamps.
- Retrieve current playback position.
- Control playback without the overhead of a full embedded player.

### 2.3 Rendering Pipeline (`VideoRenderer`)
The renderer uses a hybrid approach to balance quality and speed:
- **Lossless "KEEP" Segments**: Uses `stream copy` (`-c copy`) to maintain original 4K quality without re-encoding.
- **Keyframe Snapping**: To prevent "broken" files (black frames or freezes) in H.265/HEVC, the renderer automatically snaps the start of every KEEP segment to the nearest preceding I-frame (keyframe) using `ffprobe`.
- **Parallel Export**: Utilizes `ThreadPoolExecutor` to render multiple segments simultaneously across CPU cores.
- **Concat Assembly**: Final segments are merged using the FFmpeg `concat` demuxer for a seamless final output.

## 3. User Guide

### 3.1 Workflow
1. **Load Folder**: Load the folder containing your `.mp4` and `.srt` files.
2. **Load Subtitles**: The app parses all SRTs and maps them to the virtual timeline.
3. **Navigate**: Click any subtitle line to jump the video to that exact moment.
4. **Mark Segments**:
   - Press `[` or click **Set Start** to mark the beginning of a clip.
   - Press `]` or click **Set End** to mark the end.
   - The segment is automatically added to the KEEP list.
5. **Review**: Use the **Visual Timeline** and the **Segment Table** to review your edits.
6. **Export**: Click **Export**. The app will:
   - Snap cuts to keyframes.
   - Render segments in parallel.
   - Merge them into a final high-quality video.
   - Generate a synced `.srt` file for the final output.

### 3.2 Keyboard Shortcuts
- `[` : Set Start Marker
- `]` : Set End Marker
- `Enter` : Manually add current markers as a Keep Segment

## 4. Technical Specifications

| Feature | Specification |
| :--- | :--- |
| **Language** | Python 3.x |
| **UI Framework** | PyQt6 |
| **Video Engine** | mpv (via IPC) |
| **Processing** | FFmpeg |
| **Target Codec** | H.265 / HEVC / H.264 |
| **Timebase** | 30000/1001 FPS |

## 5. Maintenance & Development
- **Entry Point**: `main.py`
- **Core Logic**: `src/video_editor/core/`
- **UI Components**: `src/video_editor/ui/`
- **Progress Report**: See `video_editor_report.md` for the current development roadmap and completed milestones.
