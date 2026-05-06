"""
Smart Cropper — Tự động cắt khung hình 16:9 sang 9:16 (Shorts/TikTok).

Sử dụng thuật toán nhận diện khuôn mặt (OpenCV) để tìm trung tâm của
chủ thể trong clip, sau đó sinh ra chuỗi bộ lọc FFmpeg (crop filter).
Với các clip ngắn, chúng ta sử dụng vị trí trung bình (median) để tránh
việc khung hình bị giật (jitter).
"""
import os
import statistics
from typing import Optional

import cv2

from src.core.config import SmartCropConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


class SmartCropper:
    """Class xử lý việc tính toán Smart Crop cho video."""

    def __init__(self, config: SmartCropConfig) -> None:
        self._config = config
        
        # Load Haar cascade cho nhận diện khuôn mặt cơ bản (nhanh, nhẹ)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)

    def calculate_crop_filter(
        self, 
        video_path: str, 
        target_ratio: float = 9/16
    ) -> str:
        """
        Tính toán chuỗi FFmpeg crop filter cho một video.
        
        Args:
            video_path: Đường dẫn tới video
            target_ratio: Tỷ lệ khung hình đích (mặc định 9:16)
            
        Returns:
            Chuỗi filter FFmpeg (VD: "crop=1080:1920:420:0")
        """
        if not self._config.enabled or self._config.method == "center":
            # Fallback về center crop mặc định
            return f"crop=ih*{target_ratio}:ih"
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Không thể mở video để smart crop: {video_path}")
            return f"crop=ih*{target_ratio}:ih"

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Kích thước crop mong muốn
        crop_w = int(frame_height * target_ratio)
        crop_h = frame_height

        # Nếu video đã là khung dọc hoặc tỷ lệ gần bằng, không cần crop
        if frame_width <= crop_w + 10:
            cap.release()
            return ""

        # Tính toán bước nhảy (step) để scan N frames mỗi giây
        detection_fps = max(1, self._config.detection_fps)
        frame_step = max(1, int(fps / detection_fps))
        
        face_centers_x = []
        frame_idx = 0

        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
                
            # Đổi sang Grayscale để nhận diện nhanh hơn
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Tối ưu hóa: Thu nhỏ ảnh để detect nhanh hơn
            small_gray = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
            
            faces = self._face_cascade.detectMultiScale(
                small_gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(30, 30)
            )
            
            # Lấy khuôn mặt lớn nhất (diện tích lớn nhất)
            if len(faces) > 0:
                # faces format: (x, y, w, h) trên ảnh thu nhỏ
                largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
                x, y, w, h = largest_face
                
                # Scale lại tọa độ x trung tâm lên ảnh gốc
                center_x = (x + w / 2) * 2
                face_centers_x.append(center_x)
                
            frame_idx += frame_step

        cap.release()

        # Tính toán tọa độ crop x dựa trên median của các khuôn mặt
        if face_centers_x:
            median_center_x = statistics.median(face_centers_x)
            logger.debug(f"Smart Crop: Tìm thấy {len(face_centers_x)} khuôn mặt, median X = {median_center_x}")
            
            # Tính toán crop_x sao cho khuôn mặt nằm ở giữa, không vượt quá viền ảnh
            crop_x = int(median_center_x - (crop_w / 2))
            crop_x = max(0, min(crop_x, frame_width - crop_w))
            
            return f"crop={crop_w}:{crop_h}:{crop_x}:0"
            
        else:
            logger.debug("Smart Crop: Không tìm thấy khuôn mặt, sử dụng Center Crop.")
            return f"crop=ih*{target_ratio}:ih"

