from __future__ import annotations

import logging
import os
from dataclasses import asdict
from pathlib import Path

from app.classifier.inference import (
    TARGET_CLASSIFIER_LABELS,
    apply_context_penalty,
    build_detection_context,
)
from app.classifier.model import PrototypeModel
from app.classifier.dataset import append_labeled_feature_row
from app.core.config import Settings
from app.core.time_utils import utc_now_iso
from app.detection.base import DogDetector
from app.detection.factory import build_detector
from app.events.clip_saver import EventClipSaver
from app.events.event_extractor import EventExtractor, ExtractorConfig
from app.features.extractor import FeatureExtractor
from app.ingest.factory import build_frame_source
from app.ingest.frame_source import FrameSource
from app.ingest.motion_gate import MotionGate
from app.notify.factory import build_notifier
from app.pose.base import PoseEstimator
from app.pose.mock_pose_estimator import MockPoseEstimator
from app.rules.rise_failure_rules import RiseFailureRuleConfig, RiseFailureRuleEngine
from app.storage.alert_deduplicator import AlertDeduplicator
from app.storage.local_store import JsonFileStore

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(
        self,
        frame_source: FrameSource,
        detector: DogDetector,
        extractor: EventExtractor,
        pose_estimator: PoseEstimator,
        feature_extractor: FeatureExtractor,
        rule_engine: RiseFailureRuleEngine,
        notifier,
        store: JsonFileStore,
        clip_saver: EventClipSaver,
        motion_gate: MotionGate,
        deduplicator: AlertDeduplicator,
        settings: Settings,
        classifier_model_path: Path | None = None,
    ) -> None:
        self.frame_source = frame_source
        self.detector = detector
        self.extractor = extractor
        self.pose_estimator = pose_estimator
        self.feature_extractor = feature_extractor
        self.rule_engine = rule_engine
        self.notifier = notifier
        self.store = store
        self.clip_saver = clip_saver
        self.motion_gate = motion_gate
        self.deduplicator = deduplicator
        self.settings = settings
        self.classifier_model_path = classifier_model_path
        self._classifier_model: PrototypeModel | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "PipelineOrchestrator":
        frame_source = build_frame_source(settings.ingest, settings.cameras)
        detector = build_detector(settings.detection)
        extractor = EventExtractor(
            ExtractorConfig(
                event_gap_seconds=settings.pipeline.event_gap_seconds,
                min_event_seconds=settings.pipeline.min_event_seconds,
            )
        )
        pose_estimator = MockPoseEstimator()
        feature_extractor = FeatureExtractor()
        rule_engine = RiseFailureRuleEngine(
            RiseFailureRuleConfig(
                failed_attempt_min_attempts=settings.rules.failed_attempt_min_attempts,
                failed_attempt_min_duration_seconds=settings.rules.failed_attempt_min_duration_seconds,
                min_body_lift_ratio=settings.rules.min_body_lift_ratio,
                max_progress_ratio=settings.rules.max_progress_ratio,
            )
        )
        notifier = build_notifier(settings.notifier)
        store = JsonFileStore()
        clip_saver = EventClipSaver(enable_clip_capture=settings.pipeline.enable_clip_capture)
        motion_gate = MotionGate(settings.motion_gate)
        deduplicator = AlertDeduplicator(cooldown_seconds=settings.pipeline.alert_cooldown_seconds)
        classifier_model_path = settings.storage.exports_dir / "models" / "prototype_classifier.json"
        return cls(
            frame_source=frame_source,
            detector=detector,
            extractor=extractor,
            pose_estimator=pose_estimator,
            feature_extractor=feature_extractor,
            rule_engine=rule_engine,
            notifier=notifier,
            store=store,
            clip_saver=clip_saver,
            motion_gate=motion_gate,
            deduplicator=deduplicator,
            settings=settings,
            classifier_model_path=classifier_model_path,
        )

    def _ensure_directories(self) -> None:
        for path in (
            self.settings.storage.artifacts_dir,
            self.settings.storage.review_queue_dir,
            self.settings.storage.exports_dir,
        ):
            Path(path).mkdir(parents=True, exist_ok=True)

    def run_once(self) -> None:
        self._ensure_directories()

        if not self.settings.pipeline.enable_clip_capture:
            self._run_snapshot_only_once()
            return

        for frame in self.frame_source.read_frames():
            for event in self.extractor.observe_timestamp(frame.timestamp_s):
                self._process_event(event)

            motion_decision = self.motion_gate.evaluate(frame)
            if not motion_decision.should_process:
                continue
            detections = self.detector.detect(frame)
            frame.detections = detections
            if any(self._is_target_detection(detection) for detection in detections):
                for event in self.extractor.add_detected_frame(frame):
                    self._process_event(event)

        for event in self.extractor.flush():
            self._process_event(event)

    def _run_snapshot_only_once(self) -> None:
        for frame in self.frame_source.read_frames():
            motion_decision = self.motion_gate.evaluate(frame)
            if not motion_decision.should_process:
                continue
            detections = self.detector.detect(frame)
            frame.detections = detections
            if any(self._is_target_detection(detection) for detection in detections):
                event = self.extractor.event_from_single_frame(frame)
                self._process_event(event)
                return

    def _process_event(self, event) -> None:
        logger.info("processing candidate event %s", event.event_id)
        captured_at = utc_now_iso()
        epoch = os.getenv("WATCHPUPPY_EVENT_EPOCH", "unknown")
        transaction_id = os.getenv("WATCHPUPPY_EVENT_TRANSACTION_ID") or None
        media_artifacts = self.clip_saver.save(
            self.settings.storage.artifacts_dir,
            event,
            epoch=epoch,
            captured_at=captured_at,
            transaction_id=transaction_id,
        )
        pose_frames = self.pose_estimator.estimate(event)
        features = self.feature_extractor.extract(event, pose_frames)
        decision = self.rule_engine.evaluate(features)
        detection_context = self._build_detection_context(event)
        classifier_result = self._classify_event(features, detection_context=detection_context)
        classifier_wants_review = (
            classifier_result is not None
            and classifier_result["label"] in TARGET_CLASSIFIER_LABELS
        )
        should_review = True or classifier_wants_review

        artifact = {
            "captured_at": captured_at,
            "event": {
                "event_id": event.event_id,
                "camera_id": event.camera_id,
                "start_s": event.start_s,
                "end_s": event.end_s,
                "duration_s": event.duration_s,
                "frame_count": len(event.frames),
            },
            "media": {
                "event_dir": str(media_artifacts.event_dir),
                "clip_path": str(media_artifacts.clip_path) if media_artifacts.clip_path else None,
                "snapshot_path": str(media_artifacts.snapshot_path) if media_artifacts.snapshot_path else None,
            },
            "features": features.to_dict(),
            "detection_context": detection_context,
            "decision": {
                **asdict(decision),
                "should_review": should_review,
            },
            "classifier": classifier_result,
        }
        self.store.write(media_artifacts.event_dir / "metadata.json", artifact)

        label = decision.label
        append_labeled_feature_row(self.settings.storage.exports_dir / "feature_dataset.csv", features, label)

        if should_review:
            self.store.write(self.settings.storage.review_queue_dir / f"{event.event_id}.json", artifact)

        if decision.should_alert and self.deduplicator.should_send("failed_get_up_attempt", event.end_s):
            title = "Dog Rise Alert"
            body = (
                f"event={event.event_id}\n"
                f"duration={features.duration_s:.1f}s\n"
                f"attempts={features.attempt_count}\n"
                f"progress_ratio={features.progress_ratio}\n"
                f"reasons={', '.join(decision.reasons)}"
            )
            self.notifier.send(title, body)

    def _classify_event(self, features, *, detection_context: dict[str, object]) -> dict[str, object] | None:
        model = self._load_classifier_model()
        if model is None:
            return None
        raw_label, raw_score = model.predict(features.to_dict())
        label, score, penalty_reasons, penalty_factor = apply_context_penalty(
            raw_label,
            raw_score,
            detection_context=detection_context,
        )
        return {
            "label": label,
            "score": score,
            "raw_label": raw_label,
            "raw_score": raw_score,
            "context_penalty_factor": penalty_factor,
            "context_penalty_reasons": penalty_reasons,
            "context_labels": detection_context.get("non_dog_labels", []),
            "model_path": str(self.classifier_model_path) if self.classifier_model_path else None,
        }

    def _load_classifier_model(self) -> PrototypeModel | None:
        cached_model = getattr(self, "_classifier_model", None)
        if cached_model is not None:
            return cached_model
        classifier_model_path = getattr(self, "classifier_model_path", None)
        if classifier_model_path is None or not Path(classifier_model_path).exists():
            return None
        self._classifier_model = PrototypeModel.load(classifier_model_path)
        return self._classifier_model

    def _is_target_detection(self, detection) -> bool:
        return (
            detection.label in set(self.settings.detection.dog_class_names)
            and detection.confidence >= self.settings.pipeline.detector_confidence_threshold
        )

    def _build_detection_context(self, event) -> dict[str, object]:
        detection_settings = getattr(self.settings, "detection", None)
        dog_labels = set(getattr(detection_settings, "dog_class_names", ["dog"]))
        detections_by_frame = [
            [
                {
                    "label": detection.label,
                    "confidence": detection.confidence,
                }
                for detection in getattr(frame, "detections", [])
            ]
            for frame in event.frames
        ]
        return build_detection_context(
            dog_labels=dog_labels,
            detections_by_frame=detections_by_frame,
        )
