"""
Folder watcher for real-time video processing.
Monitors a folder for new video files and processes them automatically.
"""

import time
from pathlib import Path
from typing import Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from rich.console import Console

from src.utils import process_single_video


class VideoFileHandler(FileSystemEventHandler):
    """Handles file system events for video files."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        """
        Initialize file handler.
        
        Args:
            config: Configuration dictionary
            verbose: Enable verbose output
        """
        self.config = config
        self.verbose = verbose
        self.console = Console()
        self.processed_files = set()
        self.extensions = config.get("video_extensions", [".mp4", ".mkv", ".avi", ".mov", ".DVR.mp4"])
    
    def on_created(self, event: FileCreatedEvent):
        """
        Handle file creation event.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if file has video extension
        if not any(file_path.name.endswith(ext) or file_path.name.endswith(ext.upper()) for ext in self.extensions):
            return
        
        # Avoid processing the same file multiple times
        if file_path in self.processed_files:
            return
        
        # Wait a bit for file to be fully written (especially for large files)
        time.sleep(2)
        
        if not file_path.exists():
            return
        
        # Check file size to ensure it's not still being written
        initial_size = file_path.stat().st_size
        time.sleep(1)
        if file_path.stat().st_size != initial_size:
            # File is still being written, wait more
            time.sleep(5)
        
        self.console.print(f"[green]New video file detected: {file_path.name}[/green]")
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        self.console.print(f"[cyan]File size: {file_size_mb:.2f} MB[/cyan]")
        
        try:
            process_single_video(file_path, self.config, self.verbose)
            self.processed_files.add(file_path)
            self.console.print(f"[green]Completed processing: {file_path.name}[/green]\n")
        except Exception as e:
            self.console.print(f"[red]Error processing {file_path.name}: {e}[/red]\n")


class FolderWatcher:
    """Watches a folder for new video files."""
    
    def __init__(self, folder_path: Path, config: Dict[str, Any], verbose: bool = False):
        """
        Initialize folder watcher.
        
        Args:
            folder_path: Path to folder to watch
            config: Configuration dictionary
            verbose: Enable verbose output
        """
        self.folder_path = Path(folder_path)
        self.config = config
        self.verbose = verbose
        self.console = Console()
        self.observer = None
        self.event_handler = VideoFileHandler(config, verbose)
    
    def start(self):
        """Start watching the folder."""
        if not self.folder_path.exists():
            self.console.print(f"[red]Error: Folder does not exist: {self.folder_path}[/red]")
            return
        
        self.console.print(f"[green]Starting to watch: {self.folder_path}[/green]")
        
        # Process existing files first
        extensions = self.config.get("video_extensions", [".mp4", ".mkv", ".avi", ".mov", ".DVR.mp4"])
        existing_files = []
        for ext in extensions:
            existing_files.extend(self.folder_path.glob(f"*{ext}"))
            existing_files.extend(self.folder_path.glob(f"*{ext.upper()}"))
        
        if existing_files:
            self.console.print(f"[cyan]Found {len(existing_files)} existing video file(s), processing...[/cyan]")
            for video_file in sorted(existing_files):
                try:
                    process_single_video(video_file, self.config, self.verbose)
                    self.event_handler.processed_files.add(video_file)
                except Exception as e:
                    self.console.print(f"[red]Error processing {video_file.name}: {e}[/red]")
        
        # Start watching for new files
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.folder_path), recursive=False)
        self.observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop watching the folder."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.console.print("[yellow]Watcher stopped[/yellow]")

