from __future__ import annotations

from app.core.config import DetectionSettings
from app.detection.base import DogDetector
from app.detection.hailo_hef_detector import HailoHefDogDetector, HailoHefDogDetectorConfig
from app.detection.mock_detector import MockDogDetector
from app.detection.opencv_dnn_detector import OpenCVDnnDogDetector, OpenCVDnnDogDetectorConfig


def build_detector(settings: DetectionSettings) -> DogDetector:
    if settings.backend == "mock":
        return MockDogDetector()

    if settings.backend == "opencv_dnn":
        return OpenCVDnnDogDetector(
            OpenCVDnnDogDetectorConfig(
                model_path=settings.model_path,
                config_path=settings.config_path,
                labels_path=settings.labels_path,
                dog_class_names=settings.dog_class_names,
                context_class_names=settings.context_class_names,
                confidence_threshold=settings.confidence_threshold,
                input_width=settings.input_width,
                input_height=settings.input_height,
                scale_factor=settings.scale_factor,
                swap_rb=settings.swap_rb,
            )
        )

    if settings.backend == "hailo_hef":
        return HailoHefDogDetector(
            HailoHefDogDetectorConfig(
                model_path=settings.model_path,
                labels_path=settings.labels_path,
                dog_class_names=settings.dog_class_names,
                context_class_names=settings.context_class_names,
                confidence_threshold=settings.confidence_threshold,
                input_width=settings.input_width,
                input_height=settings.input_height,
                stream_interface=settings.stream_interface,
            )
        )

    raise ValueError(f"unsupported detection backend: {settings.backend}")
