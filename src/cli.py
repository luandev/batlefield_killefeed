"""
Command-line interface for Battlefield Killfeed Analyzer.
"""

from pathlib import Path
from typing import Optional
import click
from rich.console import Console

from src.utils import load_config, process_single_video


@click.group()
def cli():
    """Battlefield Killfeed Analyzer - Detect and index killfeed events from video recordings."""
    pass


@cli.command()
@click.argument("video_path", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to config file")
@click.option("--clip", is_flag=True, help="Extract video clips for detected events")
def analyze(video_path: Path, verbose: bool, config: Optional[Path], clip: bool):
    """
    Analyze a single video file.
    
    VIDEO_PATH: Path to the video file to analyze
    """
    cfg = load_config(config)
    if clip:
        # Enable clipping if --clip flag is used
        if "clipping" not in cfg:
            cfg["clipping"] = {}
        cfg["clipping"]["enabled"] = True
    process_single_video(video_path, cfg, verbose)


@cli.command()
@click.argument("folder_path", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to config file")
@click.option("--clip", is_flag=True, help="Extract video clips for detected events")
def batch(folder_path: Path, verbose: bool, config: Optional[Path], clip: bool):
    """
    Process all video files in a folder.
    
    FOLDER_PATH: Path to folder containing video files
    """
    cfg = load_config(config)
    if clip:
        # Enable clipping if --clip flag is used
        if "clipping" not in cfg:
            cfg["clipping"] = {}
        cfg["clipping"]["enabled"] = True
    console = Console()
    
    # Get video extensions from config
    extensions = cfg.get("video_extensions", [".mp4", ".mkv", ".avi", ".mov", ".DVR.mp4"])
    
    # Find all video files
    video_files = []
    for ext in extensions:
        video_files.extend(folder_path.glob(f"*{ext}"))
        video_files.extend(folder_path.glob(f"*{ext.upper()}"))
    
    if not video_files:
        console.print(f"[yellow]No video files found in {folder_path}[/yellow]")
        return
    
    console.print(f"[green]Found {len(video_files)} video file(s) to process[/green]")
    
    for video_file in sorted(video_files):
        console.print(f"\n[cyan]Processing: {video_file.name}[/cyan]")
        
        try:
            process_single_video(video_file, cfg, verbose)
        except Exception as e:
            console.print(f"[red]Error processing {video_file.name}: {e}[/red]")
            continue
    
    console.print(f"\n[green]Batch processing complete![/green]")


@cli.command()
@click.argument("folder_path", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to config file")
def watch(folder_path: Path, verbose: bool, config: Optional[Path]):
    """
    Watch a folder for new video files and process them automatically.
    
    FOLDER_PATH: Path to folder to watch
    """
    from src.watcher import FolderWatcher
    from rich.console import Console
    
    cfg = load_config(config)
    console = Console()
    
    console.print(f"[green]Watching folder: {folder_path}[/green]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    
    watcher = FolderWatcher(folder_path, cfg, verbose)
    
    try:
        watcher.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/yellow]")
        watcher.stop()


if __name__ == "__main__":
    cli()

