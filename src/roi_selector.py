"""
Interactive ROI (Region of Interest) selector for killfeed detection.
Allows visual selection of the killfeed region on a video frame.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import json
import time
from rich.console import Console


class ROISelector:
    """Interactive ROI selector using OpenCV."""
    
    def __init__(self):
        """Initialize ROI selector."""
        self.console = Console()
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.roi_selected = False
        self.current_frame = None
        self.original_frame = None
    
    def select_roi(self, video_path: Path, frame_number: int = 0) -> Optional[Tuple[int, int, int, int]]:
        """
        Interactively select ROI from a video frame.
        
        Args:
            video_path: Path to video file
            frame_number: Frame number to use for selection (default: 0)
            
        Returns:
            Tuple of (x, y, width, height) in pixels, or None if cancelled
        """
        if not video_path.exists():
            self.console.print(f"[red]Error: Video file not found: {video_path}[/red]")
            return None
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.console.print(f"[red]Error: Could not open video: {video_path}[/red]")
            return None
        
        try:
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Clamp frame number
            frame_number = max(0, min(frame_number, total_frames - 1))
            
            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if not ret:
                self.console.print(f"[red]Error: Could not read frame {frame_number}[/red]")
                return None
            
            self.original_frame = frame.copy()
            self.current_frame = frame.copy()
            
            # Create window
            window_name = "ROI Selector - Click and drag to select killfeed region"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 1280, 720)
            
            # Set mouse callback
            cv2.setMouseCallback(window_name, self._mouse_callback)
            
            self.console.print("\n[green]ROI Selection Instructions:[/green]")
            self.console.print("1. Click and drag to select the killfeed region")
            self.console.print("2. Press 'r' to reset selection")
            self.console.print("3. Press and hold 'n' for next frame (speeds up), 'p' for previous frame")
            self.console.print("4. Press 's' to save and exit")
            self.console.print("5. Press 'q' or ESC to cancel")
            self.console.print(f"\n[cyan]Current frame: {frame_number}/{total_frames - 1} ({frame_number/fps:.2f}s)[/cyan]")
            
            current_frame_num = frame_number
            key_press_start = None
            last_key = None
            last_update_time = time.time()
            update_interval = 0.05  # Update every 50ms for smooth navigation
            
            def calculate_frame_skip(hold_time: float) -> int:
                """
                Calculate frame skip amount based on hold time (logarithmic).
                
                Args:
                    hold_time: Time key has been held in seconds
                    
                Returns:
                    Number of frames to skip
                """
                if hold_time < 0.1:
                    return 1  # Start with 1 frame
                # Logarithmic: log10(hold_time * 10 + 1) * multiplier
                # This gives: 0.1s = 1 frame, 0.5s = ~2 frames, 1s = ~3 frames, 2s = ~4 frames, etc.
                skip = int(np.log10(hold_time * 10 + 1) * 10)
                return max(1, min(skip, 1000))  # Cap at 1000 frames per update
            
            while True:
                display_frame = self.current_frame.copy()
                
                # Draw current selection
                if self.start_point and self.end_point:
                    x1, y1 = self.start_point
                    x2, y2 = self.end_point
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Draw ROI info
                    roi_width = abs(x2 - x1)
                    roi_height = abs(y2 - y1)
                    info_text = f"ROI: {roi_width}x{roi_height} at ({min(x1,x2)}, {min(y1,y2)})"
                    cv2.putText(display_frame, info_text, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Draw frame info and speed indicator
                frame_info = f"Frame: {current_frame_num}/{total_frames - 1} | Time: {current_frame_num/fps:.2f}s"
                if key_press_start:
                    hold_time = time.time() - key_press_start
                    speed = calculate_frame_skip(hold_time)
                    frame_info += f" | Speed: {speed}x"
                cv2.putText(display_frame, frame_info, (10, height - 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                cv2.imshow(window_name, display_frame)
                
                # Check for key press
                key = cv2.waitKey(1) & 0xFF
                current_time = time.time()
                
                # Handle key press/release
                if key == ord('q') or key == 27:  # ESC
                    cv2.destroyAllWindows()
                    self.console.print("[yellow]ROI selection cancelled[/yellow]")
                    return None
                
                elif key == ord('s'):
                    if self.start_point and self.end_point:
                        x1, y1 = self.start_point
                        x2, y2 = self.end_point
                        x = min(x1, x2)
                        y = min(y1, y2)
                        w = abs(x2 - x1)
                        h = abs(y2 - y1)
                        cv2.destroyAllWindows()
                        return (x, y, w, h)
                    else:
                        self.console.print("[yellow]Please select a region first[/yellow]")
                
                elif key == ord('r'):
                    self.start_point = None
                    self.end_point = None
                    self.current_frame = self.original_frame.copy()
                    key_press_start = None
                    last_key = None
                
                elif key == ord('n'):
                    # Next frame - start tracking if new press
                    if last_key != 'n':
                        key_press_start = time.time()
                        last_key = 'n'
                        # Immediately advance 1 frame on first press
                        current_frame_num = min(current_frame_num + 1, total_frames - 1)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_num)
                        ret, frame = cap.read()
                        if ret:
                            self.original_frame = frame.copy()
                            self.current_frame = frame.copy()
                            self.start_point = None
                            self.end_point = None
                        last_update_time = current_time
                    # Update frame based on hold time (for held keys)
                    elif current_time - last_update_time >= update_interval:
                        hold_time = current_time - key_press_start
                        frame_skip = calculate_frame_skip(hold_time)
                        current_frame_num = min(current_frame_num + frame_skip, total_frames - 1)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_num)
                        ret, frame = cap.read()
                        if ret:
                            self.original_frame = frame.copy()
                            self.current_frame = frame.copy()
                            self.start_point = None
                            self.end_point = None
                        last_update_time = current_time
                
                elif key == ord('p'):
                    # Previous frame - start tracking if new press
                    if last_key != 'p':
                        key_press_start = time.time()
                        last_key = 'p'
                        # Immediately advance 1 frame on first press
                        current_frame_num = max(0, current_frame_num - 1)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_num)
                        ret, frame = cap.read()
                        if ret:
                            self.original_frame = frame.copy()
                            self.current_frame = frame.copy()
                            self.start_point = None
                            self.end_point = None
                        last_update_time = current_time
                    # Update frame based on hold time (for held keys)
                    elif current_time - last_update_time >= update_interval:
                        hold_time = current_time - key_press_start
                        frame_skip = calculate_frame_skip(hold_time)
                        current_frame_num = max(0, current_frame_num - frame_skip)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_num)
                        ret, frame = cap.read()
                        if ret:
                            self.original_frame = frame.copy()
                            self.current_frame = frame.copy()
                            self.start_point = None
                            self.end_point = None
                        last_update_time = current_time
                
                else:
                    # Key released - reset tracking
                    if key_press_start is not None:
                        key_press_start = None
                        last_key = None
        
        finally:
            cap.release()
            cv2.destroyAllWindows()
    
    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for ROI selection."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.end_point = (x, y)
        
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.end_point = (x, y)
                # Update display
                self.current_frame = self.original_frame.copy()
                if self.start_point:
                    cv2.rectangle(self.current_frame, self.start_point, self.end_point, (0, 255, 0), 2)
        
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)
    
    def save_roi_to_config(
        self,
        roi: Tuple[int, int, int, int],
        video_path: Path,
        config_path: Path
    ) -> bool:
        """
        Save ROI to config.json as percentages (resolution-independent).
        
        The ROI is saved as percentages relative to video dimensions, making it
        work across different video resolutions. The same ROI percentages will
        work for 1080p, 1440p, 4K, etc.
        
        Args:
            roi: Tuple of (x, y, width, height) in pixels (from current video)
            video_path: Path to video file (to get dimensions for conversion)
            config_path: Path to config.json
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Get video dimensions
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.console.print(f"[red]Error: Could not open video to get dimensions[/red]")
            return False
        
        try:
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            cap.release()
        
        x, y, w, h = roi
        
        # Convert to percentages (resolution-independent)
        roi_x_percent = x / video_width
        roi_y_percent = y / video_height
        roi_width_percent = w / video_width
        roi_height_percent = h / video_height
        
        # Load existing config
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Update ROI settings (percentages are the primary, resolution-independent values)
        if "detection" not in config:
            config["detection"] = {}
        
        config["detection"]["roi_x_percent"] = roi_x_percent
        config["detection"]["roi_y_percent"] = roi_y_percent
        config["detection"]["roi_width_percent"] = roi_width_percent
        config["detection"]["roi_height_percent"] = roi_height_percent
        
        # Save pixel coordinates for reference only (not used by detector)
        config["detection"]["roi_pixels_reference"] = {
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "video_width": video_width,
            "video_height": video_height,
            "note": "Reference only - detector uses percentages above"
        }
        
        # Save config
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.console.print(f"\n[green]ROI saved to {config_path}[/green]")
            self.console.print(f"[cyan]Resolution-independent ROI (percentages):[/cyan]")
            self.console.print(f"[cyan]  x={roi_x_percent:.4f} ({roi_x_percent*100:.2f}%), y={roi_y_percent:.4f} ({roi_y_percent*100:.2f}%)[/cyan]")
            self.console.print(f"[cyan]  width={roi_width_percent:.4f} ({roi_width_percent*100:.2f}%), height={roi_height_percent:.4f} ({roi_height_percent*100:.2f}%)[/cyan]")
            self.console.print(f"[dim]Reference: Selected from {video_width}x{video_height} video as ({x}, {y}) - {w}x{h} pixels[/dim]")
            self.console.print(f"[green]This ROI will work with any video resolution![/green]")
            return True
        except Exception as e:
            self.console.print(f"[red]Error saving config: {e}[/red]")
            return False

