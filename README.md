# Battlefield Killfeed Analyzer

Tool to scan Battlefield 6 (2042) recordings, detect killfeed white boxes, and build an indexed timeline of events (kills, headshots, multikills, etc.) with comprehensive progress tracking for large video files.

## Features

- **Video Processing**: Analyzes Battlefield 6 DVR recordings (NVIDIA ShadowPlay)
- **Killfeed Detection**: Detects white box entries in the bottom-left killfeed region
- **Event Indexing**: Groups detections into events (KILL, MULTI_KILL, etc.)
- **Progress Tracking**: Rich terminal output with progress bars, statistics, and verbose logging
- **Batch Processing**: Process multiple videos in a folder
- **Folder Watching**: Automatically process new videos as they're added
- **Export Formats**: CSV and JSON output with full detection data
- **Video Clipping**: Extract highlight clips around detected events
- **Event Visualizer**: View events timeline, statistics, and visualize on video with overlays
- **Interactive ROI Selector**: Visually set the killfeed detection region with click-and-drag interface
- **Terminal UI**: Browse videos in default folder with processing status indicators

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

### Setting ROI (Region of Interest)

The easiest way to set the ROI is using the interactive selector:

```bash
python main.py set-roi "path/to/video.mp4"
```

Start from a specific frame (useful if killfeed appears later in video):

```bash
python main.py set-roi "path/to/video.mp4" --frame 1000
```

**Interactive Controls:**
- **Click and drag** to select the killfeed region
- **'n'** - Next frame (hold to speed up logarithmically)
- **'p'** - Previous frame (hold to speed up logarithmically)
- **'r'** - Reset selection
- **'s'** - Save and exit
- **'q'** or **ESC** - Cancel

**Speed Control:** When holding 'n' or 'p', the frame skip speed increases logarithmically:
- Short press: 1 frame at a time
- Hold 0.5s: ~2 frames per update
- Hold 1s: ~3 frames per update
- Hold 2s: ~4 frames per update
- And so on (capped at 1000 frames per update)

The current speed multiplier is displayed in the frame info.

The ROI will be automatically saved to `config.json` as **percentages (resolution-independent)**. This means the same ROI will work across different video resolutions (1080p, 1440p, 4K, etc.) without needing to be reconfigured.

Alternatively, edit `config.json` manually:

- **ROI Settings**: Adjust `roi_x_percent`, `roi_y_percent`, `roi_width_percent`, `roi_height_percent` for killfeed position
- **Detection Thresholds**: Modify `brightness_threshold`, `min_area`, `max_area` for sensitivity
- **Sampling Rate**: Set `sample_fps` to control frame sampling (lower = faster processing)
- **Event Grouping**: Adjust `grouping_delta_t` to merge detections within time window
- **Video Clipping**: Configure `clipping` section to extract highlight clips (see below)

### BF6 Killfeed Configuration

The default configuration is set for Battlefield 6 (2042) killfeed:
- Position: Bottom-left, lower-left from center
- Boxes stack horizontally, pushing left as new ones appear
- ROI: x=0.0-35%, y=65-90% of screen (percentages are resolution-independent)

**Important:** ROI is stored as percentages relative to video dimensions, so the same configuration works for any video resolution. If you set ROI on a 1440p video, it will automatically work for 1080p, 4K, or any other resolution.

## Usage

### Browse Videos (Terminal UI)

List all videos in the default folder with processing status:

```bash
python main.py browse
```

This displays:
- All video files in `D:\Videos\NVIDIA\Battlefield 6` (or folder from config)
- File sizes
- Processing status (✓ Processed, ~ Partial, ○ Pending)
- File sizes in MB

Use a custom folder:

```bash
python main.py browse --folder "path/to/videos"
```

### Analyze a Single Video

```bash
python -m src.cli analyze "path/to/video.mp4"
```

With verbose output:

```bash
python -m src.cli analyze "path/to/video.mp4" --verbose
```

### Batch Process a Folder

```bash
python -m src.cli batch "D:\Videos\NVIDIA\Battlefield 6"
```

### Watch a Folder for New Videos

```bash
python -m src.cli watch "D:\Videos\NVIDIA\Battlefield 6"
```

This will:
1. Process any existing videos in the folder
2. Automatically process new videos as they're added
3. Press Ctrl+C to stop

### Extract Video Clips

Extract highlight clips around detected events:

```bash
python -m src.cli analyze "path/to/video.mp4" --clip
```

Or enable in `config.json`:
```json
"clipping": {
  "enabled": true,
  "pre_padding_seconds": 2.0,
  "post_padding_seconds": 2.0,
  "cluster_threshold_seconds": 5.0,
  "min_confidence": 0.5,
  "min_box_count": 1,
  "allowed_tags": ["MULTI_KILL", "KILL"],
  "max_clips": null
}
```

**Clustering**: Events that occur within `cluster_threshold_seconds` of each other are automatically grouped into a single clip. This prevents creating many small clips when events happen in quick succession.

**Clip Filenames**: 
- Single event: `{video_id}_{index}_{tag}_{timestamp}.mp4`
- Clustered events: `{video_id}_{index}_{tag}x{count}_{timestamp}.mp4`

Clips are saved to `output/clips/` directory.

### Visualize Detected Events

View detected events from a JSON file:

```bash
python -m src.cli visualize "output/video_events.json"
```

Show events on video with overlays:

```bash
python -m src.cli visualize "output/video_events.json" --video "path/to/video.mp4"
```

Show specific event details:

```bash
python -m src.cli visualize "output/video_events.json" --details 1
```

Show specific event on video:

```bash
python -m src.cli visualize "output/video_events.json" --video "video.mp4" --event 1
```

**Visualizer Features:**
- Summary statistics (total events, duration, breakdown by tag)
- Visual timeline showing event positions
- Detailed events table with timestamps and confidence
- Video playback with event overlays (when `--video` is provided)
- Keyboard controls: `q` to quit, `n` for next event, `p` for previous, `space` to pause

### Custom Config File

```bash
python -m src.cli analyze "video.mp4" --config custom_config.json
```

## Output

Results are saved to the `output` folder (configurable in `config.json`):

- **CSV**: `{video_id}_events.csv` - Summary of events in spreadsheet format
- **JSON**: `{video_id}_events.json` - Full detection data with all boxes
- **Clips**: `clips/{video_id}_{index}_{tag}_{timestamp}.mp4` - Video clips around events (if clipping enabled)

### CSV Format

| video_id | start_frame | end_frame | start_time | end_time | box_count | stack_slot_min | stack_slot_max | tag_guess | confidence |
|----------|-------------|-----------|------------|----------|-----------|---------------|----------------|-----------|------------|
| video_001 | 100 | 150 | 1.67 | 2.50 | 3 | 0 | 2 | MULTI_KILL | 0.85 |

### JSON Format

Includes full detection data with bounding boxes, timestamps, and stack positions for each event.

## Event Types

The analyzer classifies events as:

- **KILL**: Single box detection
- **MULTI_KILL**: Multiple boxes detected (configurable threshold, default: 3+)
- **UNKNOWN**: Default fallback for unclassified events

Future versions will support:
- HEADSHOT (via OCR/pattern matching)
- KILL_ASSIST
- SUPPRESSION_ASSIST
- VEHICLE_KILL
- OBJECTIVE_KILL

## Performance

- **Sampling Rate**: Default 3 FPS (configurable) - balances speed vs accuracy
- **Progress Tracking**: Real-time progress bars, ETA, processing speed
- **Memory Usage**: Monitors memory consumption for large videos
- **Verbose Mode**: Detailed statistics per frame (use `--verbose` flag)

## Example Video Format

Designed for NVIDIA ShadowPlay DVR recordings:
- Format: MP4 (`.DVR.mp4` extension)
- Resolution: 2560x1440 (1440p) typical
- Frame Rate: 60 FPS
- Codec: H264 (MPEG-4 AVC)

## Troubleshooting

### No Detections Found

1. Check ROI settings in `config.json` - killfeed position may vary
2. Adjust `brightness_threshold` (try lower values like 180-190)
3. Verify video has killfeed visible in bottom-left region
4. Use `--verbose` flag to see detection statistics

### Processing Too Slow

1. Reduce `sample_fps` in config (e.g., 2.0 instead of 3.0)
2. Increase `min_area` to filter smaller false positives
3. Disable verbose mode for faster processing

### Memory Issues

- The tool monitors memory usage automatically
- For very large videos, consider processing in smaller chunks
- Close other applications to free up RAM

## Development

Project structure:

```
battlefield_killfeed/
├── src/
│   ├── detector.py      # White box detection
│   ├── processor.py    # Video processing pipeline
│   ├── indexer.py      # Event grouping and export
│   ├── watcher.py      # Folder monitoring
│   ├── logger.py       # Progress tracking
│   └── cli.py          # Command-line interface
├── config.json         # Configuration
├── requirements.txt    # Dependencies
└── README.md           # This file
```

## License

MIT License

