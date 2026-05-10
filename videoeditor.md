# Smart-Cut Video Editor

## High-Performance Lossless Editing based on Speech Navigation

### 1. Overview

The goal of this project is to create a specialized video editing tool for long-form recordings (e.g., DJI bike rides) where the primary markers of interest are spoken words. The application will use AI-generated subtitles (SRT) as a navigation map to quickly identify "Keep" zones (original quality) and "Gap" zones (compressed into fast timelapses).

### 2. Key Requirements

- **No Full Re-encoding:** Maintain original 4K quality for "Keep" segments using `stream copy`.

- **Smart Timelapses:** Automatically convert intervals between "Keep" zones into fixed-duration (e.g., 10 seconds) timelapses.

- **Speech-Driven Navigation:** A GUI that allows jumping to specific video timestamps by clicking on subtitle text.

- **High Rendering Performance:** Use frame-dropping techniques for timelapses to avoid decoding every single frame.


### 3. Tech Stack

- **Language:** Python 3.x

- **GUI Framework:** PyQt6 or PySide6

- **Video Preview Engine:** `mpv` (via JSON-RPC/IPC socket)

- **Processing Engine:** `ffmpeg`

- **Input Files:** Video (MP4/MOV) and Subtitles (SRT)


### 4. Architecture & UI Layout

#### A. Interface Structure (Split Window)

1. **Left Panel (Subtitle Navigator):**

   - A scrollable list of all subtitle entries.

   - Format: `\[Timestamp\] Text`.

   - **Interaction:** Clicking an entry sends a `seek` command to the `mpv` instance.

2. **Right Panel (Preview Window):**

   - Embedded `mpv` player window.

   - Renders video with the SRT file loaded as an overlay for visual confirmation.

3. **Bottom Panel (Segment Manager):**

   - Visual timeline showing "Keep" and "Gap" zones.

   - Controls: `Set Start`, `Set End`, `Add Keep Segment`, `Clear All`.

   - Final `Export` button.

#### B. Data Model

The application manages a sorted list of segments:

- **KEEP:** `(start\_time, end\_time)` $\\rightarrow$ Copy original stream.

- **GAP:** `(start\_time, end\_time)` $\\rightarrow$ Calculate speed factor $\\rightarrow$ Render as 10s timelapse.


### 5. Technical Implementation Pipeline

#### Phase 1: Preview & Navigation

- Start `mpv` with an IPC socket: `mpv --input-ipc-server=/tmp/mpvsocket`.

- Use Python to send JSON commands to the socket (e.g., `\{"command": \["set\_property", "time-pos", 120.5\]\}`).

- Parse SRT file into a list of objects containing `start`, `end`, and `text`.

#### Phase 2: Segment Selection

- User defines `Keep` intervals using the player's current timestamp.

- App automatically fills the holes between `Keep` intervals as `Gap` intervals.

#### Phase 3: The Rendering Engine (Hybrid Method)

To maximize speed and quality, the app generates a sequence of `ffmpeg` commands:

1. **For KEEP segments (Lossless):**

```
ffmpeg -ss \[start\] -to \[end\] -i input.mp4 -c copy segment\_keep\_N.mp4
```

2. **For GAP segments (Optimized Timelapse):**

   - Calculate `SpeedFactor = (End - Start) / 10`.

   - Use the `select` filter to drop frames and `setpts` to adjust timing:

```
ffmpeg -ss \[start\] -to \[end\] -i input.mp4 -vf "select='not(mod(n,\[SpeedFactor\]))',setpts=\[1/SpeedFactor\]\*PTS" -an segment\_gap\_N.mp4
```

3. **Final Assembly (Concat):**

   - Create a `list.txt` containing all generated `.mp4` chunks.

   - Perform a final lossless merge:

```
ffmpeg -f concat -safe 0 -i list.txt -c copy final\_output.mp4
```


### 6. Development Roadmap

#### Stage 1: Foundation (MVP)

- [ ] Implement PyQt6 basic layout.

- [ ] Implement SRT parser.

- [ ] Integrate `mpv` via IPC for click-to-jump functionality.

#### Stage 2: Selection Logic

- [ ] Implement "Set Start/End" functionality.

- [ ] Create the segment list manager (Keep/Gap logic).

- [ ] Basic timeline visualization.

#### Stage 3: Rendering Backend

- [ ] Implement the `ffmpeg` wrapper for Lossless Copy.

- [ ] Implement the `ffmpeg` wrapper for Optimized Timelapses.

- [ ] Implement the final `concat` assembly process.

#### Stage 4: Polish & UX

- [ ] Add progress bars for rendering.

- [ ] Add "Dry Run" mode to preview the segment list before exporting.

- [ ] Error handling for file paths and codec mismatches.

