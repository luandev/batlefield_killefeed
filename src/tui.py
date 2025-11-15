"""
Terminal UI for browsing and selecting videos.
Interactive interface using Rich for video file management.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
import time


class VideoBrowser:
    """Interactive terminal UI for browsing and selecting videos."""
    
    def __init__(self, default_folder: Optional[Path] = None):
        """
        Initialize video browser.
        
        Args:
            default_folder: Default folder to browse (if None, uses config or asks user)
        """
        self.console = Console()
        self.default_folder = default_folder
        self.video_extensions = [".mp4", ".mkv", ".avi", ".mov", ".DVR.mp4"]
    
    def load_config(self, config_path: Path = Path("config.json")) -> Dict[str, Any]:
        """Load configuration file."""
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def get_video_folder(self) -> Optional[Path]:
        """Get video folder from config or default."""
        if self.default_folder:
            folder_path = Path(self.default_folder)
            if folder_path.exists():
                return folder_path
            self.console.print(f"[yellow]Warning: Specified folder does not exist: {folder_path}[/yellow]")
        
        config = self.load_config()
        
        # Try watch_folder first, then check for default
        watch_folder = config.get("watch_folder", "")
        if watch_folder:
            folder_path = Path(watch_folder)
            if folder_path.exists():
                return folder_path
            self.console.print(f"[yellow]Warning: watch_folder in config does not exist: {folder_path}[/yellow]")
        
        # Default folder
        default = Path(r"D:\Videos\NVIDIA\Battlefield 6")
        if default.exists():
            return default
        
        # If default doesn't exist, return it anyway so user can see the path
        return default
    
    def find_videos(self, folder: Path) -> List[Path]:
        """
        Find all video files in folder.
        
        Args:
            folder: Folder to search
            
        Returns:
            List of video file paths
        """
        if not folder.exists():
            return []
        
        video_files = []
        for ext in self.video_extensions:
            video_files.extend(folder.glob(f"*{ext}"))
            video_files.extend(folder.glob(f"*{ext.upper()}"))
        
        return sorted(video_files)
    
    def get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """
        Get basic info about a video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video info
        """
        try:
            size_mb = video_path.stat().st_size / (1024 * 1024)
            return {
                "name": video_path.name,
                "size_mb": size_mb,
                "exists": True
            }
        except Exception:
            return {
                "name": video_path.name,
                "size_mb": 0,
                "exists": False
            }
    
    def display_video_list(self, videos: List[Path], selected_index: int = 0):
        """
        Display list of videos in a table.
        
        Args:
            videos: List of video file paths
            selected_index: Currently selected video index
        """
        if not videos:
            self.console.print("[yellow]No video files found in folder[/yellow]")
            return
        
        table = Table(title="Video Files", show_header=True, header_style="bold magenta", show_lines=False)
        table.add_column("#", style="cyan", width=5, justify="right")
        table.add_column("Filename", style="green", width=60)
        table.add_column("Size", style="yellow", width=12, justify="right")
        table.add_column("Status", style="blue", width=10)
        
        for idx, video_path in enumerate(videos):
            info = self.get_video_info(video_path)
            size_str = f"{info['size_mb']:.1f} MB"
            
            # Check if events file exists
            output_dir = Path("output")
            video_id = video_path.stem
            events_json = output_dir / f"{video_id}_events.json"
            events_csv = output_dir / f"{video_id}_events.csv"
            
            status = ""
            if events_json.exists() and events_csv.exists():
                status = "✓ Processed"
            elif events_json.exists() or events_csv.exists():
                status = "~ Partial"
            else:
                status = "○ Pending"
            
            # Highlight selected row
            if idx == selected_index:
                table.add_row(
                    f"[bold cyan]{idx + 1}[/bold cyan]",
                    f"[bold green]{info['name']}[/bold green]",
                    f"[bold yellow]{size_str}[/bold yellow]",
                    f"[bold blue]{status}[/bold blue]"
                )
            else:
                table.add_row(
                    str(idx + 1),
                    info['name'],
                    size_str,
                    status
                )
        
        self.console.print(table)
    
    def interactive_browser(self) -> Optional[Path]:
        """
        Interactive video browser with keyboard navigation.
        
        Returns:
            Selected video path or None if cancelled
        """
        folder = self.get_video_folder()
        
        if not folder:
            folder_str = Prompt.ask(
                "Enter video folder path",
                default=str(Path(r"D:\Videos\NVIDIA\Battlefield 6"))
            )
            folder = Path(folder_str)
        
        if not folder.exists():
            self.console.print(f"[red]Error: Folder does not exist: {folder}[/red]")
            return None
        
        videos = self.find_videos(folder)
        
        if not videos:
            self.console.print(f"[yellow]No video files found in {folder}[/yellow]")
            return None
        
        selected_index = 0
        
        self.console.print(f"\n[green]Found {len(videos)} video file(s) in {folder}[/green]")
        self.console.print("[dim]Use arrow keys to navigate, Enter to select, 'q' to quit[/dim]\n")
        
        # Simple interactive loop (Rich doesn't have built-in keyboard input for this)
        # We'll use a simpler approach with prompts
        while True:
            self.console.clear()
            self.console.print(f"[bold cyan]Video Browser - {folder}[/bold cyan]\n")
            self.display_video_list(videos, selected_index)
            
            self.console.print("\n[dim]Commands:[/dim]")
            self.console.print("  [cyan]↑/↓[/cyan] or [cyan]j/k[/cyan] - Navigate")
            self.console.print("  [cyan]Enter[/cyan] - Select video")
            self.console.print("  [cyan]a[/cyan] - Analyze selected video")
            self.console.print("  [cyan]v[/cyan] - Visualize events (if processed)")
            self.console.print("  [cyan]r[/cyan] - Set ROI")
            self.console.print("  [cyan]q[/cyan] - Quit")
            
            choice = Prompt.ask(
                "\n[bold]Action[/bold]",
                choices=["up", "down", "j", "k", "enter", "a", "v", "r", "q"],
                default="enter"
            )
            
            if choice in ["q", "quit"]:
                return None
            
            elif choice in ["up", "k"]:
                selected_index = max(0, selected_index - 1)
            
            elif choice in ["down", "j"]:
                selected_index = min(len(videos) - 1, selected_index + 1)
            
            elif choice == "enter":
                return videos[selected_index]
            
            elif choice == "a":
                return videos[selected_index]  # Return for analysis
            
            elif choice == "v":
                video = videos[selected_index]
                video_id = video.stem
                events_json = Path("output") / f"{video_id}_events.json"
                if events_json.exists():
                    return events_json  # Return JSON path for visualization
                else:
                    self.console.print("[yellow]No events file found. Process video first.[/yellow]")
                    time.sleep(1)
            
            elif choice == "r":
                return videos[selected_index]  # Return for ROI selection
    
    def simple_list(self, folder: Optional[Path] = None) -> List[Path]:
        """
        Simple list display of videos (non-interactive).
        
        Args:
            folder: Folder to list (uses default if None)
            
        Returns:
            List of video paths
        """
        if folder is None:
            folder = self.get_video_folder()
        
        if not folder:
            self.console.print(f"[red]Error: No video folder specified or found[/red]")
            self.console.print(f"[dim]Set 'watch_folder' in config.json or use --folder option[/dim]")
            return []
        
        if not folder.exists():
            self.console.print(f"[red]Error: Folder does not exist: {folder}[/red]")
            self.console.print(f"[dim]Please check the path or update config.json[/dim]")
            return []
        
        videos = self.find_videos(folder)
        
        if not videos:
            self.console.print(f"[yellow]No video files found in {folder}[/yellow]")
            self.console.print(f"[dim]Looking for: {', '.join(self.video_extensions)}[/dim]")
            return []
        
        self.console.print(f"\n[bold cyan]Video Browser[/bold cyan]")
        self.console.print(f"[dim]Folder: {folder}[/dim]\n")
        self.console.print(f"[green]Found {len(videos)} video file(s)[/green]\n")
        self.display_video_list(videos)
        
        return videos

