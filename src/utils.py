"""
Utility functions shared across modules.
"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

from src.processor import VideoProcessor
from src.indexer import EventIndexer
from src.logger import ProgressTracker
from src.clipper import VideoClipper


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to config file (default: config.json in current directory)
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path("config.json")
    
    if not config_path.exists():
        console = Console()
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_video_id(video_path: Path) -> str:
    """
    Extract video ID from file path (filename without extension).
    
    Args:
        video_path: Path to video file
        
    Returns:
        Video ID string
    """
    return video_path.stem


def process_single_video(
    video_path: Path,
    config: Dict[str, Any],
    verbose: bool = False
):
    """
    Process a single video file.
    
    Args:
        video_path: Path to video file
        config: Configuration dictionary
        verbose: Enable verbose output
    """
    console = Console()
    
    if not video_path.exists():
        console.print(f"[red]Error: Video file not found: {video_path}[/red]")
        sys.exit(1)
    
    video_id = get_video_id(video_path)
    output_dir = Path(config.get("output_folder", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    log_level = config.get("verbosity", {}).get("log_level", "INFO")
    if verbose:
        log_level = "DEBUG"
    
    with ProgressTracker(verbose=verbose, log_level=log_level) as progress:
        # Process video
        processor = VideoProcessor(config)
        detections = processor.process_video(video_path, progress)
        
        if not detections:
            console.print("[yellow]No detections found in video.[/yellow]")
            return
        
        # Group detections into events
        indexer = EventIndexer(config)
        events = indexer.group_detections(detections, video_id, progress)
        
        if not events:
            console.print("[yellow]No events created from detections.[/yellow]")
            return
        
        # Export results
        output_files = {}
        
        if config.get("export", {}).get("export_csv", True):
            csv_path = output_dir / f"{video_id}_events.csv"
            indexer.export_to_csv(events, csv_path, progress)
            output_files["CSV"] = csv_path
        
        if config.get("export", {}).get("export_json", True):
            json_path = output_dir / f"{video_id}_events.json"
            indexer.export_to_json(events, json_path, progress)
            output_files["JSON"] = json_path
        
        # Extract video clips if enabled
        if config.get("clipping", {}).get("enabled", False):
            clipper = VideoClipper(config)
            clip_paths = clipper.extract_clips(video_path, events, output_dir, progress)
            if clip_paths:
                output_files["Clips"] = clip_paths[0].parent  # Directory containing clips
        
        # Display summary
        total_time = progress.progress.tasks[0].elapsed if progress.progress and progress.progress.tasks else 0
        progress.display_summary(total_time, [e.to_dict() for e in events], output_files)

