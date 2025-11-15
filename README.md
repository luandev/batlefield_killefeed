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

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.json` to adjust detection parameters:

- **ROI Settings**: Adjust `roi_x_percent`, `roi_y_percent`, `roi_width_percent`, `roi_height_percent` for killfeed position
- **Detection Thresholds**: Modify `brightness_threshold`, `min_area`, `max_area` for sensitivity
- **Sampling Rate**: Set `sample_fps` to control frame sampling (lower = faster processing)
- **Event Grouping**: Adjust `grouping_delta_t` to merge detections within time window
- **Video Clipping**: Configure `clipping` section to extract highlight clips (see below)

### BF6 Killfeed Configuration

The default configuration is set for Battlefield 6 (2042) killfeed:
- Position: Bottom-left, lower-left from center
- Boxes stack horizontally, pushing left as new ones appear
- ROI: x=0.0-35%, y=65-90% of screen

## Usage

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

