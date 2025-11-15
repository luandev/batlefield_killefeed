"""
Video visualizer for displaying detected events and cuts.
Loads JSON events file and displays timeline, event details, and optional video playback.
"""

import json
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn


class EventVisualizer:
    """Visualizes detected events from JSON file."""
    
    def __init__(self):
        """Initialize visualizer."""
        self.console = Console()
        self.events_data = None
        self.video_id = None
        self.events = []
    
    def load_json(self, json_path: Path) -> bool:
        """
        Load events from JSON file.
        
        Args:
            json_path: Path to JSON events file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if not json_path.exists():
            self.console.print(f"[red]Error: JSON file not found: {json_path}[/red]")
            return False
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.events_data = json.load(f)
            
            self.video_id = self.events_data.get("video_id", "Unknown")
            self.events = self.events_data.get("events", [])
            
            self.console.print(f"[green]Loaded {len(self.events)} events from {json_path.name}[/green]")
            return True
        except Exception as e:
            self.console.print(f"[red]Error loading JSON: {e}[/red]")
            return False
    
    def display_summary(self):
        """Display summary of all events."""
        if not self.events:
            self.console.print("[yellow]No events to display[/yellow]")
            return
        
        # Calculate total duration
        if self.events:
            total_duration = max(event.get("end_time", 0) for event in self.events)
        else:
            total_duration = 0
        
        # Count events by tag
        tag_counts = {}
        for event in self.events:
            tag = event.get("tag_guess", "UNKNOWN")
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Create summary table
        summary_table = Table(title=f"Events Summary: {self.video_id}", show_header=True, header_style="bold magenta")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Total Events", str(len(self.events)))
        summary_table.add_row("Total Duration", f"{total_duration:.2f} seconds ({total_duration/60:.2f} minutes)")
        
        # Add tag breakdown
        for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
            summary_table.add_row(f"{tag} Events", str(count))
        
        self.console.print("\n")
        self.console.print(summary_table)
    
    def display_timeline(self, width: int = 80):
        """
        Display a visual timeline of events.
        
        Args:
            width: Width of timeline in characters
        """
        if not self.events:
            return
        
        # Calculate total duration
        total_duration = max(event.get("end_time", 0) for event in self.events)
        if total_duration == 0:
            return
        
        # Create timeline
        timeline_text = Text()
        timeline_text.append("Timeline: ", style="bold cyan")
        
        # Color map for different event types
        tag_colors = {
            "KILL": "red",
            "MULTI_KILL": "bright_red",
            "HEADSHOT": "yellow",
            "KILL_ASSIST": "blue",
            "UNKNOWN": "white"
        }
        
        # Draw timeline
        timeline_chars = [' '] * width
        timeline_labels = []
        
        for event in self.events:
            start_time = event.get("start_time", 0)
            end_time = event.get("end_time", 0)
            tag = event.get("tag_guess", "UNKNOWN")
            
            # Calculate position on timeline
            start_pos = int((start_time / total_duration) * width)
            end_pos = int((end_time / total_duration) * width)
            start_pos = max(0, min(start_pos, width - 1))
            end_pos = max(0, min(end_pos, width - 1))
            
            # Get color for tag
            color = tag_colors.get(tag, "white")
            
            # Mark timeline
            for i in range(start_pos, end_pos + 1):
                if i < width:
                    timeline_chars[i] = '█'
            
            # Store label
            timeline_labels.append({
                "pos": start_pos,
                "tag": tag,
                "time": f"{start_time:.1f}s",
                "color": color
            })
        
        # Build timeline string
        timeline_str = ''.join(timeline_chars)
        timeline_text.append(timeline_str, style="green")
        
        self.console.print("\n")
        self.console.print(timeline_text)
        
        # Add time markers
        time_markers = Text()
        for i in range(0, width, width // 10):
            time_val = (i / width) * total_duration
            time_markers.append(f"{time_val:.0f}s", style="dim")
            if i < width - 5:
                time_markers.append(" " * (width // 10 - len(f"{time_val:.0f}s")), style="dim")
        
        self.console.print(time_markers)
    
    def display_events_table(self, limit: Optional[int] = None):
        """
        Display events in a detailed table.
        
        Args:
            limit: Maximum number of events to display (None for all)
        """
        if not self.events:
            return
        
        events_to_show = self.events[:limit] if limit else self.events
        
        table = Table(title="Detected Events", show_header=True, header_style="bold yellow")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Time", style="green", width=12)
        table.add_column("Duration", style="blue", width=10)
        table.add_column("Tag", style="magenta", width=12)
        table.add_column("Boxes", style="yellow", width=8)
        table.add_column("Confidence", style="red", width=10)
        
        for idx, event in enumerate(events_to_show, 1):
            start_time = event.get("start_time", 0)
            end_time = event.get("end_time", 0)
            duration = end_time - start_time
            tag = event.get("tag_guess", "UNKNOWN")
            box_count = event.get("box_count", 0)
            confidence = event.get("confidence", 0)
            
            time_str = f"{start_time:.1f}s - {end_time:.1f}s"
            duration_str = f"{duration:.2f}s"
            confidence_str = f"{confidence:.2f}"
            
            table.add_row(
                str(idx),
                time_str,
                duration_str,
                tag,
                str(box_count),
                confidence_str
            )
        
        self.console.print("\n")
        self.console.print(table)
        
        if limit and len(self.events) > limit:
            self.console.print(f"\n[yellow]Showing first {limit} of {len(self.events)} events. Use --limit to see more.[/yellow]")
    
    def display_event_details(self, event_index: int):
        """
        Display detailed information about a specific event.
        
        Args:
            event_index: Index of event (1-based)
        """
        if not self.events or event_index < 1 or event_index > len(self.events):
            self.console.print(f"[red]Invalid event index: {event_index}[/red]")
            return
        
        event = self.events[event_index - 1]
        
        details_table = Table(title=f"Event #{event_index} Details", show_header=True, header_style="bold blue")
        details_table.add_column("Property", style="cyan")
        details_table.add_column("Value", style="green")
        
        details_table.add_row("Tag", event.get("tag_guess", "UNKNOWN"))
        details_table.add_row("Start Time", f"{event.get('start_time', 0):.2f} seconds")
        details_table.add_row("End Time", f"{event.get('end_time', 0):.2f} seconds")
        details_table.add_row("Duration", f"{event.get('end_time', 0) - event.get('start_time', 0):.2f} seconds")
        details_table.add_row("Start Frame", str(event.get("start_frame", 0)))
        details_table.add_row("End Frame", str(event.get("end_frame", 0)))
        details_table.add_row("Box Count", str(event.get("box_count", 0)))
        details_table.add_row("Stack Slot Range", f"{event.get('stack_slot_range', [0, 0])[0]} - {event.get('stack_slot_range', [0, 0])[1]}")
        details_table.add_row("Confidence", f"{event.get('confidence', 0):.4f}")
        details_table.add_row("Detections", str(len(event.get("detections", []))))
        
        self.console.print("\n")
        self.console.print(details_table)
    
    def visualize_video(self, video_path: Path, event_index: Optional[int] = None):
        """
        Visualize events on video with overlays.
        
        Args:
            video_path: Path to source video
            event_index: Optional specific event to show, or None for all
        """
        if not video_path.exists():
            self.console.print(f"[red]Error: Video file not found: {video_path}[/red]")
            return
        
        if not self.events:
            self.console.print("[yellow]No events to visualize[/yellow]")
            return
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.console.print(f"[red]Error: Could not open video: {video_path}[/red]")
            return
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Filter events to show
            if event_index:
                if event_index < 1 or event_index > len(self.events):
                    self.console.print(f"[red]Invalid event index: {event_index}[/red]")
                    return
                events_to_show = [self.events[event_index - 1]]
            else:
                events_to_show = self.events
            
            self.console.print(f"[green]Visualizing {len(events_to_show)} event(s) on video[/green]")
            self.console.print("[yellow]Press 'q' to quit, 'n' for next event, 'p' for previous, space to pause[/yellow]")
            
            current_event_idx = 0
            paused = False
            
            while current_event_idx < len(events_to_show):
                event = events_to_show[current_event_idx]
                start_frame = event.get("start_frame", 0)
                end_frame = event.get("end_frame", 0)
                
                # Seek to event start
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                
                frame_num = start_frame
                frame_delay = int(1000 / fps) if fps > 0 else 33  # Delay in milliseconds
                
                while frame_num <= end_frame:
                    if not paused:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        
                        # Draw overlay
                        frame = self._draw_event_overlay(frame, event, frame_num, fps)
                        
                        # Display frame
                        window_name = f"Event #{current_event_idx + 1}: {event.get('tag_guess', 'UNKNOWN')}"
                        cv2.imshow(window_name, frame)
                        
                        frame_num += 1
                    
                    # Handle keyboard input with appropriate delay
                    key = cv2.waitKey(frame_delay) & 0xFF
                    if key == ord('q'):
                        cap.release()
                        cv2.destroyAllWindows()
                        return
                    elif key == ord('n'):
                        current_event_idx += 1
                        break
                    elif key == ord('p'):
                        current_event_idx = max(0, current_event_idx - 1)
                        break
                    elif key == ord(' '):
                        paused = not paused
                
                if frame_num > end_frame:
                    current_event_idx += 1
            
            cv2.destroyAllWindows()
            
        finally:
            cap.release()
    
    def _draw_event_overlay(self, frame: np.ndarray, event: Dict, frame_num: int, fps: float) -> np.ndarray:
        """
        Draw event overlay on frame.
        
        Args:
            frame: Video frame
            event: Event data
            frame_num: Current frame number
            fps: Video frame rate
            
        Returns:
            Frame with overlay
        """
        overlay = frame.copy()
        
        # Get event info
        tag = event.get("tag_guess", "UNKNOWN")
        time_sec = frame_num / fps
        box_count = event.get("box_count", 0)
        confidence = event.get("confidence", 0)
        
        # Color based on tag
        tag_colors = {
            "KILL": (0, 0, 255),  # Red
            "MULTI_KILL": (0, 0, 200),  # Darker red
            "HEADSHOT": (0, 255, 255),  # Yellow
            "KILL_ASSIST": (255, 0, 0),  # Blue
            "UNKNOWN": (255, 255, 255)  # White
        }
        color = tag_colors.get(tag, (255, 255, 255))
        
        # Draw border
        cv2.rectangle(overlay, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), color, 5)
        
        # Draw info text
        info_text = [
            f"Event: {tag}",
            f"Time: {time_sec:.2f}s",
            f"Boxes: {box_count}",
            f"Confidence: {confidence:.2f}"
        ]
        
        y_offset = 30
        for text in info_text:
            cv2.putText(overlay, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            y_offset += 25
        
        # Blend overlay
        alpha = 0.3
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
        
        return frame

