from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
import importlib
import os

from app.core.config import CameraSettings, Settings


@dataclass(slots=True)
class OnvifProbeTarget:
    camera_id: str
    host: str
    username: str
    password: str
    rtsp_url: str


def resolve_probe_target(settings: Settings, camera_id: str) -> OnvifProbeTarget:
    camera = _select_camera(settings.cameras, camera_id)
    if camera is None:
        raise ValueError(f"camera_id not found or disabled: {camera_id}")
    return _build_probe_target(camera)


def discover_wsdl_dir(explicit_dir: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit_dir:
        candidates.append(Path(explicit_dir))

    env_dir = os.getenv("ONVIF_WSDL_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    try:
        onvif_module = importlib.import_module("onvif")
        module_dir = Path(onvif_module.__file__).resolve().parent
        candidates.append(module_dir / "wsdl")
    except ImportError:
        pass

    candidates.extend(
        [
            Path("/etc/onvif/wsdl"),
            Path("/usr/local/share/onvif/wsdl"),
            Path("/usr/share/onvif/wsdl"),
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = ", ".join(str(path) for path in candidates)
    raise RuntimeError(
        "unable to locate ONVIF WSDL directory. "
        "Pass --wsdl-dir, set ONVIF_WSDL_DIR, or install onvif-zeep with bundled WSDL files. "
        f"Searched: {searched}"
    )


def _select_camera(cameras: list[CameraSettings], requested_id: str) -> CameraSettings | None:
    for camera in cameras:
        if not camera.enabled:
            continue
        if camera.camera_id == requested_id or requested_id in camera.aliases:
            return camera
    return None


def _build_probe_target(camera: CameraSettings) -> OnvifProbeTarget:
    parsed = urlparse(camera.rtsp_url)
    if not parsed.hostname:
        raise ValueError(f"camera rtsp_url does not include a hostname: {camera.rtsp_url}")
    if parsed.username is None or parsed.password is None:
        raise ValueError(
            "camera rtsp_url must include username and password for ONVIF probe reuse: "
            f"{camera.rtsp_url}"
        )

    return OnvifProbeTarget(
        camera_id=camera.camera_id,
        host=parsed.hostname,
        username=unquote(parsed.username),
        password=unquote(parsed.password),
        rtsp_url=camera.rtsp_url,
    )
