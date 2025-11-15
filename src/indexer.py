"""
Event indexing and grouping module.
Groups detections into events and exports to CSV/JSON.
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

from src.detector import Detection
from src.logger import ProgressTracker


@dataclass
class Event:
    """Represents a grouped event (kill, multikill, etc.)."""
    video_id: str
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    box_count: int
    stack_slot_range: tuple
    tag_guess: str
    confidence: float
    detections: List[Detection]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "video_id": self.video_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "box_count": self.box_count,
            "stack_slot_range": self.stack_slot_range,
            "tag_guess": self.tag_guess,
            "confidence": self.confidence,
            "detections": [det.to_dict() for det in self.detections]
        }


class EventIndexer:
    """Groups detections into events and exports results."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize event indexer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.detection_config = config.get("detection", {})
    
    def group_detections(
        self,
        detections: List[Detection],
        video_id: str,
        progress_tracker: ProgressTracker
    ) -> List[Event]:
        """
        Group detections into events based on time proximity.
        
        Args:
            detections: List of detections
            video_id: Video identifier
            progress_tracker: Progress tracker instance
            
        Returns:
            List of grouped events
        """
        if not detections:
            return []
        
        delta_t = self.detection_config.get("grouping_delta_t", 0.8)
        
        # Sort detections by time
        sorted_detections = sorted(detections, key=lambda d: d.time_sec)
        
        grouping_task = progress_tracker.create_task(
            "Grouping detections into events",
            total=len(sorted_detections)
        )
        
        events = []
        current_group = []
        
        for detection in sorted_detections:
            if not current_group:
                current_group.append(detection)
            else:
                # Check if detection is within time window of current group
                last_time = current_group[-1].time_sec
                if detection.time_sec - last_time <= delta_t:
                    current_group.append(detection)
                else:
                    # Create event from current group
                    event = self._create_event(current_group, video_id)
                    if event:
                        events.append(event)
                    current_group = [detection]
            
            progress_tracker.update_task(grouping_task, advance=1)
        
        # Handle remaining group
        if current_group:
            event = self._create_event(current_group, video_id)
            if event:
                events.append(event)
        
        progress_tracker.stats["events_created"] = len(events)
        progress_tracker.log_info(f"Created {len(events)} events from {len(detections)} detections")
        
        return events
    
    def _create_event(self, detections: List[Detection], video_id: str) -> Optional[Event]:
        """
        Create an event from a group of detections.
        
        Args:
            detections: List of detections in the group
            video_id: Video identifier
            
        Returns:
            Event object or None if invalid
        """
        if not detections:
            return None
        
        start_frame = min(d.frame for d in detections)
        end_frame = max(d.frame for d in detections)
        start_time = min(d.time_sec for d in detections)
        end_time = max(d.time_sec for d in detections)
        
        stack_slots = [d.stack_slot for d in detections]
        stack_slot_range = (min(stack_slots), max(stack_slots))
        
        # Calculate average confidence
        avg_confidence = sum(d.confidence for d in detections) / len(detections)
        
        # Classify event
        tag_guess = self._classify_event(detections)
        
        return Event(
            video_id=video_id,
            start_frame=start_frame,
            end_frame=end_frame,
            start_time=start_time,
            end_time=end_time,
            box_count=len(detections),
            stack_slot_range=stack_slot_range,
            tag_guess=tag_guess,
            confidence=avg_confidence,
            detections=detections
        )
    
    def _classify_event(self, detections: List[Detection]) -> str:
        """
        Classify event type based on detection characteristics.
        
        Args:
            detections: List of detections in the event
            
        Returns:
            Event tag (KILL, MULTI_KILL, etc.)
        """
        box_count = len(detections)
        min_boxes_for_multikill = self.detection_config.get("min_boxes_for_multikill", 3)
        
        if box_count >= min_boxes_for_multikill:
            return "MULTI_KILL"
        elif box_count == 1:
            return "KILL"
        else:
            return "UNKNOWN"
    
    def export_to_csv(
        self,
        events: List[Event],
        output_path: Path,
        progress_tracker: ProgressTracker
    ):
        """
        Export events to CSV file.
        
        Args:
            events: List of events
            output_path: Output file path
            progress_tracker: Progress tracker instance
        """
        if not events:
            progress_tracker.log_warning("No events to export")
            return
        
        export_task = progress_tracker.create_task(
            f"Exporting to CSV: {output_path.name}",
            total=len(events)
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "video_id", "start_frame", "end_frame", "start_time", "end_time",
                "box_count", "stack_slot_min", "stack_slot_max", "tag_guess", "confidence"
            ])
            writer.writeheader()
            
            for event in events:
                writer.writerow({
                    "video_id": event.video_id,
                    "start_frame": event.start_frame,
                    "end_frame": event.end_frame,
                    "start_time": event.start_time,
                    "end_time": event.end_time,
                    "box_count": event.box_count,
                    "stack_slot_min": event.stack_slot_range[0],
                    "stack_slot_max": event.stack_slot_range[1],
                    "tag_guess": event.tag_guess,
                    "confidence": event.confidence
                })
                progress_tracker.update_task(export_task, advance=1)
        
        file_size = output_path.stat().st_size
        progress_tracker.log_info(f"Exported {len(events)} events to CSV ({file_size / 1024:.2f} KB)")
    
    def export_to_json(
        self,
        events: List[Event],
        output_path: Path,
        progress_tracker: ProgressTracker
    ):
        """
        Export events to JSON file with full detection data.
        
        Args:
            events: List of events
            output_path: Output file path
            progress_tracker: Progress tracker instance
        """
        if not events:
            progress_tracker.log_warning("No events to export")
            return
        
        export_task = progress_tracker.create_task(
            f"Exporting to JSON: {output_path.name}",
            total=len(events)
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        events_data = [event.to_dict() for event in events]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "video_id": events[0].video_id if events else "",
                "total_events": len(events),
                "events": events_data
            }, f, indent=2, ensure_ascii=False)
        
        progress_tracker.update_task(export_task, advance=len(events))
        
        file_size = output_path.stat().st_size
        progress_tracker.log_info(f"Exported {len(events)} events to JSON ({file_size / 1024:.2f} KB)")

