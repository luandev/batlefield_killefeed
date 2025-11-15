"""
Logging and progress tracking system for Battlefield Killfeed Analyzer.
Uses Rich library for enhanced terminal output, progress bars, and tables.
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.logging import RichHandler
import psutil
import os


@dataclass
class VideoInfo:
    """Video metadata container."""
    fps: float
    frame_count: int
    duration: float
    width: int
    height: int
    file_size: int
    codec: Optional[str] = None


class ProgressTracker:
    """Manages progress bars and verbose logging for video processing."""
    
    def __init__(self, verbose: bool = False, log_level: str = "INFO"):
        """
        Initialize progress tracker.
        
        Args:
            verbose: Enable verbose output
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.verbose = verbose
        self.console = Console()
        self.progress = None
        self.start_time = None
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=self.console, rich_tracebacks=True)]
        )
        self.logger = logging.getLogger("battlefield_killfeed")
        
        # Statistics
        self.stats = {
            "frames_processed": 0,
            "detections_found": 0,
            "events_created": 0,
            "processing_speed": 0.0,
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True
        )
        self.progress.__enter__()
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)
    
    def create_task(self, description: str, total: Optional[int] = None) -> int:
        """
        Create a new progress task.
        
        Args:
            description: Task description
            total: Total number of items (None for indeterminate)
            
        Returns:
            Task ID
        """
        if self.progress:
            return self.progress.add_task(description, total=total)
        return 0
    
    def update_task(self, task_id: int, advance: int = 1, **kwargs):
        """
        Update a progress task.
        
        Args:
            task_id: Task ID
            advance: Amount to advance
            **kwargs: Additional update parameters
        """
        if self.progress:
            self.progress.update(task_id, advance=advance, **kwargs)
    
    def display_video_info(self, video_info: VideoInfo, video_path: Path):
        """
        Display video metadata in a formatted table.
        
        Args:
            video_info: Video metadata
            video_path: Path to video file
        """
        table = Table(title=f"Video Information: {video_path.name}", show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Resolution", f"{video_info.width}x{video_info.height}")
        table.add_row("Frame Rate", f"{video_info.fps:.2f} FPS")
        table.add_row("Total Frames", f"{video_info.frame_count:,}")
        table.add_row("Duration", f"{video_info.duration:.2f} seconds ({video_info.duration/60:.2f} minutes)")
        table.add_row("File Size", f"{video_info.file_size / (1024**3):.2f} GB")
        if video_info.codec:
            table.add_row("Codec", video_info.codec)
        
        self.console.print(table)
    
    def display_memory_usage(self):
        """Display current memory usage."""
        if not self.verbose:
            return
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        self.logger.debug(f"Memory usage: {memory_mb:.2f} MB")
    
    def display_detection_stats(self, frame_num: int, detections: int, elapsed: float):
        """
        Display detection statistics for current frame.
        
        Args:
            frame_num: Current frame number
            detections: Number of detections in this frame
            elapsed: Elapsed time
        """
        if not self.verbose:
            return
        
        self.logger.debug(f"Frame {frame_num}: {detections} detections found (elapsed: {elapsed:.2f}s)")
    
    def display_summary(self, total_time: float, events: list, output_files: Dict[str, Path]):
        """
        Display final processing summary.
        
        Args:
            total_time: Total processing time
            events: List of events found
            output_files: Dictionary of output file paths
        """
        table = Table(title="Processing Summary", show_header=True, header_style="bold green")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Processing Time", f"{total_time:.2f} seconds")
        table.add_row("Frames Processed", f"{self.stats['frames_processed']:,}")
        table.add_row("Detections Found", f"{self.stats['detections_found']:,}")
        table.add_row("Events Created", f"{len(events):,}")
        
        if self.stats['frames_processed'] > 0:
            avg_detections = self.stats['detections_found'] / self.stats['frames_processed']
            table.add_row("Avg Detections/Frame", f"{avg_detections:.2f}")
        
        if total_time > 0:
            fps = self.stats['frames_processed'] / total_time
            table.add_row("Processing Speed", f"{fps:.2f} frames/sec")
        
        # Event breakdown by tag
        if events:
            tag_counts = {}
            for event in events:
                tag = event.get('tag_guess', 'UNKNOWN')
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            tag_table = Table(title="Events by Tag", show_header=True, header_style="bold yellow")
            tag_table.add_column("Tag", style="cyan")
            tag_table.add_column("Count", style="green")
            
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                tag_table.add_row(tag, str(count))
            
            self.console.print("\n")
            self.console.print(tag_table)
        
        # Output files
        if output_files:
            file_table = Table(title="Output Files", show_header=True, header_style="bold blue")
            file_table.add_column("Type", style="cyan")
            file_table.add_column("Path", style="green")
            file_table.add_column("Size", style="yellow")
            
            for file_type, file_path in output_files.items():
                if file_path.exists():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    file_table.add_row(file_type, str(file_path), f"{size_mb:.2f} MB")
            
            self.console.print("\n")
            self.console.print(file_table)
        
        self.console.print("\n")
        self.console.print(table)
    
    def log_info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def log_warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def log_error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def log_debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

