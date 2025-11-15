"""
Video processing pipeline for Battlefield killfeed analysis.
Handles video loading, frame sampling, and detection coordination.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Iterator, Dict, Any, Optional
import os

from src.detector import KillfeedDetector, Detection
from src.logger import ProgressTracker, VideoInfo


class VideoProcessor:
    """Processes video files to detect killfeed events."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize video processor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.detector = KillfeedDetector(config)
        self.detection_config = config.get("detection", {})
    
    def process_video(
        self,
        video_path: Path,
        progress_tracker: ProgressTracker
    ) -> List[Detection]:
        """
        Process a video file and return all detections.
        
        Args:
            video_path: Path to video file
            progress_tracker: Progress tracker instance
            
        Returns:
            List of all detections
        """
        # Get video information
        video_info = self._get_video_info(video_path)
        if video_info is None:
            progress_tracker.log_error(f"Failed to get video info for {video_path}")
            return []
        
        # Display video info
        progress_tracker.display_video_info(video_info, video_path)
        
        # Display memory usage
        if self.config.get("verbosity", {}).get("show_memory_usage", True):
            progress_tracker.display_memory_usage()
        
        # Process frames
        all_detections = []
        sample_fps = self.detection_config.get("sample_fps", 3.0)
        
        frame_task = progress_tracker.create_task(
            f"Processing frames from {video_path.name}",
            total=video_info.frame_count
        )
        
        frame_skip = max(1, int(video_info.fps / sample_fps))
        
        for frame_num, frame, time_sec in self._sample_frames(
            video_path,
            video_info.fps,
            frame_skip,
            progress_tracker
        ):
            # Detect white boxes
            detections = self.detector.detect_white_boxes(
                frame,
                frame_num,
                time_sec,
                progress_callback=lambda fn, det_count, elapsed: (
                    progress_tracker.display_detection_stats(fn, det_count, elapsed)
                    if self.config.get("verbosity", {}).get("show_detection_stats", False)
                    else None
                )
            )
            
            all_detections.extend(detections)
            
            # Update progress
            progress_tracker.update_task(frame_task, advance=frame_skip)
            progress_tracker.stats["frames_processed"] += 1
            progress_tracker.stats["detections_found"] += len(detections)
            
            # Update processing speed
            elapsed = progress_tracker.progress.tasks[frame_task].elapsed if progress_tracker.progress else 0
            if elapsed > 0:
                progress_tracker.stats["processing_speed"] = progress_tracker.stats["frames_processed"] / elapsed
        
        progress_tracker.log_info(f"Found {len(all_detections)} total detections in {video_path.name}")
        
        return all_detections
    
    def _get_video_info(self, video_path: Path) -> Optional[VideoInfo]:
        """
        Extract video metadata.
        
        Args:
            video_path: Path to video file
            
        Returns:
            VideoInfo object or None if failed
        """
        if not video_path.exists():
            return None
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Try to get codec info
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]) if fourcc else None
            
            duration = frame_count / fps if fps > 0 else 0
            
            # Get file size
            file_size = os.path.getsize(video_path)
            
            return VideoInfo(
                fps=fps,
                frame_count=frame_count,
                duration=duration,
                width=width,
                height=height,
                file_size=file_size,
                codec=codec
            )
        finally:
            cap.release()
    
    def _sample_frames(
        self,
        video_path: Path,
        fps: float,
        frame_skip: int,
        progress_tracker: ProgressTracker
    ) -> Iterator[tuple[int, np.ndarray, float]]:
        """
        Sample frames from video at specified rate.
        
        Args:
            video_path: Path to video file
            fps: Video frame rate
            frame_skip: Number of frames to skip between samples
            progress_tracker: Progress tracker instance
            
        Yields:
            Tuples of (frame_num, frame, time_sec)
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            progress_tracker.log_error(f"Failed to open video: {video_path}")
            return
        
        try:
            frame_num = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Only process frames at sample rate
                if frame_num % frame_skip == 0:
                    time_sec = frame_num / fps
                    yield (frame_num, frame, time_sec)
                
                frame_num += 1
        finally:
            cap.release()

