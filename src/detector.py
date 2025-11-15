"""
Core white box detection module for Battlefield killfeed.
Detects bright rectangular boxes in the killfeed region.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import time


@dataclass
class Detection:
    """Represents a detected white box."""
    frame: int
    time_sec: float
    x: int
    y: int
    width: int
    height: int
    stack_slot: int
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert detection to dictionary."""
        return {
            "frame": self.frame,
            "time_sec": self.time_sec,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "stack_slot": self.stack_slot,
            "confidence": self.confidence
        }


class KillfeedDetector:
    """Detects white boxes in the killfeed region."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize detector with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.detection_config = config.get("detection", {})
    
    def detect_white_boxes(
        self,
        frame: np.ndarray,
        frame_num: int,
        time_sec: float,
        progress_callback: Optional[callable] = None
    ) -> List[Detection]:
        """
        Detect white boxes in the killfeed region.
        
        Args:
            frame: Input frame (BGR format)
            frame_num: Frame number
            time_sec: Timestamp in seconds
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of detected boxes
        """
        start_time = time.time()
        
        # Crop ROI
        cropped = self._crop_roi(frame)
        if cropped is None or cropped.size == 0:
            return []
        
        # Threshold bright regions
        binary_mask = self._threshold_bright_regions(cropped)
        
        # Find contours
        contours = self._find_contours(binary_mask)
        
        # Filter by shape
        valid_boxes = self._filter_by_shape(contours, cropped.shape)
        
        # Assign stack slots (0 = newest/rightmost)
        detections = self._assign_stack_slot(valid_boxes, frame_num, time_sec)
        
        elapsed = time.time() - start_time
        
        if progress_callback:
            progress_callback(frame_num, len(detections), elapsed)
        
        return detections
    
    def _crop_roi(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Crop the region of interest (bottom-left killfeed area).
        
        Uses percentage-based ROI coordinates, making it resolution-independent.
        The same ROI percentages work for any video resolution (1080p, 1440p, 4K, etc.).
        
        Args:
            frame: Input frame
            
        Returns:
            Cropped region or None if invalid
        """
        h, w = frame.shape[:2]
        
        # Convert percentage-based ROI to pixel coordinates for current frame resolution
        # This makes the ROI resolution-independent - same percentages work for any resolution
        roi_x = int(self.detection_config.get("roi_x_percent", 0.0) * w)
        roi_y = int(self.detection_config.get("roi_y_percent", 0.65) * h)
        roi_width = int(self.detection_config.get("roi_width_percent", 0.35) * w)
        roi_height = int(self.detection_config.get("roi_height_percent", 0.25) * h)
        
        # Ensure ROI is within frame bounds
        roi_x = max(0, min(roi_x, w - 1))
        roi_y = max(0, min(roi_y, h - 1))
        roi_width = min(roi_width, w - roi_x)
        roi_height = min(roi_height, h - roi_y)
        
        if roi_width <= 0 or roi_height <= 0:
            return None
        
        return frame[roi_y:roi_y + roi_height, roi_x:roi_x + roi_width]
    
    def _threshold_bright_regions(self, cropped: np.ndarray) -> np.ndarray:
        """
        Threshold to find bright (white) regions.
        
        Args:
            cropped: Cropped ROI image
            
        Returns:
            Binary mask of bright regions
        """
        # Convert to grayscale
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        
        # Threshold bright regions
        threshold = self.detection_config.get("brightness_threshold", 200)
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        
        # Apply morphology to clean up
        if self.detection_config.get("use_morphology", True):
            kernel_size = self.detection_config.get("morph_kernel_size", 3)
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        return binary
    
    def _find_contours(self, binary_mask: np.ndarray) -> List:
        """
        Find contours in the binary mask.
        
        Args:
            binary_mask: Binary mask image
            
        Returns:
            List of contours
        """
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours
    
    def _filter_by_shape(self, contours: List, image_shape: tuple) -> List[tuple]:
        """
        Filter contours by area and aspect ratio.
        
        Args:
            contours: List of contours
            image_shape: Shape of the cropped image (height, width)
            
        Returns:
            List of valid bounding boxes as (x, y, w, h)
        """
        valid_boxes = []
        
        min_area = self.detection_config.get("min_area", 100)
        max_area = self.detection_config.get("max_area", 5000)
        aspect_min = self.detection_config.get("aspect_ratio_min", 0.3)
        aspect_max = self.detection_config.get("aspect_ratio_max", 3.0)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if area < min_area or area > max_area:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate aspect ratio
            aspect_ratio = w / h if h > 0 else 0
            
            if aspect_ratio < aspect_min or aspect_ratio > aspect_max:
                continue
            
            # Calculate confidence based on area and aspect ratio
            # Normalize to 0-1 range
            area_confidence = min(1.0, (area - min_area) / (max_area - min_area))
            aspect_confidence = 1.0 - abs(aspect_ratio - 1.5) / 1.5  # Prefer ~1.5 aspect ratio
            aspect_confidence = max(0.0, min(1.0, aspect_confidence))
            
            confidence = (area_confidence + aspect_confidence) / 2.0
            
            valid_boxes.append((x, y, w, h, confidence))
        
        return valid_boxes
    
    def _assign_stack_slot(
        self,
        boxes: List[tuple],
        frame_num: int,
        time_sec: float
    ) -> List[Detection]:
        """
        Assign stack slots to boxes (0 = newest/rightmost, increasing left).
        
        Args:
            boxes: List of (x, y, w, h, confidence) tuples
            frame_num: Frame number
            time_sec: Timestamp in seconds
            
        Returns:
            List of Detection objects
        """
        if not boxes:
            return []
        
        # Sort by x-coordinate (rightmost = newest = slot 0)
        # In BF6, boxes push left, so rightmost is newest
        sorted_boxes = sorted(boxes, key=lambda b: b[0], reverse=True)
        
        detections = []
        for stack_slot, (x, y, w, h, confidence) in enumerate(sorted_boxes):
            detection = Detection(
                frame=frame_num,
                time_sec=time_sec,
                x=x,
                y=y,
                width=w,
                height=h,
                stack_slot=stack_slot,
                confidence=confidence
            )
            detections.append(detection)
        
        return detections

