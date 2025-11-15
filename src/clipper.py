"""
Video clipping module for extracting highlight clips around events.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

from src.indexer import Event
from src.logger import ProgressTracker


class VideoClipper:
    """Extracts video clips around detected events."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize video clipper.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.clip_config = config.get("clipping", {})
    
    def extract_clips(
        self,
        video_path: Path,
        events: List[Event],
        output_dir: Path,
        progress_tracker: ProgressTracker
    ) -> List[Path]:
        """
        Extract video clips for each event.
        
        Args:
            video_path: Path to source video
            events: List of events to extract clips for
            output_dir: Directory to save clips
            progress_tracker: Progress tracker instance
            
        Returns:
            List of output clip paths
        """
        if not events:
            return []
        
        # Filter events based on configuration
        filtered_events = self._filter_events(events)
        
        if not filtered_events:
            progress_tracker.log_warning("No events match clipping criteria")
            return []
        
        # Get video info
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            progress_tracker.log_error(f"Failed to open video: {video_path}")
            return []
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            # Try to get codec, fallback to H264 (mp4v) or use mp4v for compatibility
            if fourcc:
                codec_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
                # Use original codec if it's a valid 4-char codec, otherwise use mp4v
                codec = codec_str if len(codec_str) == 4 and codec_str.isalnum() else 'mp4v'
            else:
                codec = 'mp4v'
        finally:
            cap.release()
        
        # Create output directory
        clips_dir = output_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        
        # Cluster events that are close together
        event_clusters = self._cluster_events(filtered_events)
        
        pre_padding = self.clip_config.get("pre_padding_seconds", 2.0)
        post_padding = self.clip_config.get("post_padding_seconds", 2.0)
        
        clip_task = progress_tracker.create_task(
            f"Extracting {len(event_clusters)} clip(s) from {len(filtered_events)} event(s)",
            total=len(event_clusters)
        )
        
        output_clips = []
        
        for idx, cluster in enumerate(event_clusters):
            try:
                clip_path = self._extract_clustered_clip(
                    video_path,
                    cluster,
                    clips_dir,
                    fps,
                    width,
                    height,
                    codec,
                    pre_padding,
                    post_padding,
                    idx
                )
                if clip_path:
                    output_clips.append(clip_path)
                progress_tracker.update_task(clip_task, advance=1)
            except Exception as e:
                progress_tracker.log_error(f"Error extracting clip for cluster {idx}: {e}")
                progress_tracker.update_task(clip_task, advance=1)
                continue
        
        progress_tracker.log_info(f"Extracted {len(output_clips)} clip(s) from {len(event_clusters)} cluster(s) to {clips_dir}")
        return output_clips
    
    def _filter_events(self, events: List[Event]) -> List[Event]:
        """
        Filter events based on clipping configuration.
        
        Args:
            events: List of all events
            
        Returns:
            Filtered list of events to clip
        """
        # Get filter settings
        min_confidence = self.clip_config.get("min_confidence", 0.0)
        min_box_count = self.clip_config.get("min_box_count", 1)
        allowed_tags = self.clip_config.get("allowed_tags", [])
        max_clips = self.clip_config.get("max_clips", None)
        
        filtered = []
        
        for event in events:
            # Filter by confidence
            if event.confidence < min_confidence:
                continue
            
            # Filter by box count
            if event.box_count < min_box_count:
                continue
            
            # Filter by tag
            if allowed_tags and event.tag_guess not in allowed_tags:
                continue
            
            filtered.append(event)
        
        # Sort by confidence/box_count (best first)
        filtered.sort(key=lambda e: (e.confidence, e.box_count), reverse=True)
        
        # Limit number of clips
        if max_clips and max_clips > 0:
            filtered = filtered[:max_clips]
        
        return filtered
    
    def _cluster_events(self, events: List[Event]) -> List[List[Event]]:
        """
        Cluster events that are close together in time.
        
        Args:
            events: List of events (should be sorted by time)
            
        Returns:
            List of event clusters, where each cluster is a list of events
        """
        if not events:
            return []
        
        # Sort events by start time
        sorted_events = sorted(events, key=lambda e: e.start_time)
        
        cluster_threshold = self.clip_config.get("cluster_threshold_seconds", 5.0)
        
        clusters = []
        current_cluster = [sorted_events[0]]
        
        for event in sorted_events[1:]:
            # Check if this event is close to the last event in current cluster
            last_event = current_cluster[-1]
            time_gap = event.start_time - last_event.end_time
            
            if time_gap <= cluster_threshold:
                # Add to current cluster
                current_cluster.append(event)
            else:
                # Start a new cluster
                clusters.append(current_cluster)
                current_cluster = [event]
        
        # Add the last cluster
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    def _extract_clustered_clip(
        self,
        video_path: Path,
        cluster: List[Event],
        output_dir: Path,
        fps: float,
        width: int,
        height: int,
        codec: str,
        pre_padding: float,
        post_padding: float,
        clip_index: int
    ) -> Optional[Path]:
        """
        Extract a single clip that spans all events in a cluster.
        
        Args:
            video_path: Source video path
            cluster: List of events in the cluster
            output_dir: Output directory
            fps: Video frame rate
            width: Video width
            height: Video height
            codec: Video codec
            pre_padding: Seconds before first event
            post_padding: Seconds after last event
            clip_index: Index for filename
            
        Returns:
            Path to extracted clip or None if failed
        """
        if not cluster:
            return None
        
        # Find the earliest start time and latest end time in the cluster
        earliest_start = min(event.start_time for event in cluster)
        latest_end = max(event.end_time for event in cluster)
        
        # Calculate clip time range with padding
        start_time = max(0.0, earliest_start - pre_padding)
        end_time = latest_end + post_padding
        
        # Calculate frame range
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)
        
        # Generate output filename
        video_id = cluster[0].video_id
        # Use the most common tag or combine tags
        tags = [event.tag_guess for event in cluster]
        if len(set(tags)) == 1:
            tag = tags[0]
        else:
            # Multiple tags - use the most significant one or create a combined name
            tag_counts = {}
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
            tag = max(tag_counts.items(), key=lambda x: x[1])[0]
        
        # Include event count in filename if multiple events
        event_count_str = f"x{len(cluster)}" if len(cluster) > 1 else ""
        timestamp = f"{int(start_time):04d}s"
        clip_filename = f"{video_id}_{clip_index:03d}_{tag}{event_count_str}_{timestamp}.mp4"
        clip_path = output_dir / clip_filename
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        
        try:
            # Set starting frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Create video writer
            # Try multiple codecs for compatibility (H264, XVID, mp4v)
            fourcc = None
            codecs_to_try = ['mp4v', 'XVID', 'H264', codec if len(codec) == 4 else None]
            for codec_name in codecs_to_try:
                if codec_name:
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*codec_name)
                        break
                    except:
                        continue
            
            if fourcc is None:
                # Final fallback
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            
            out = cv2.VideoWriter(
                str(clip_path),
                fourcc,
                fps,
                (width, height)
            )
            
            if not out.isOpened():
                return None
            
            # Read and write frames
            current_frame = start_frame
            while current_frame <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                out.write(frame)
                current_frame += 1
            
            out.release()
            
            # Verify file was created and has content
            if clip_path.exists() and clip_path.stat().st_size > 0:
                return clip_path
            else:
                if clip_path.exists():
                    clip_path.unlink()
                return None
                
        finally:
            cap.release()

