from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from xml.etree import ElementTree
from xml.etree.ElementTree import tostring


NS = {"tt": "http://www.onvif.org/ver10/schema"}


@dataclass(slots=True)
class OnvifEvent:
    topic: str
    utc_time: datetime | None
    property_operation: str | None
    source: dict[str, str]
    data: dict[str, str]
    raw: dict[str, Any]


@dataclass(slots=True)
class TriggerDecision:
    should_trigger: bool
    trigger_key: str | None
    reason: str | None


def parse_notification_message(message: dict[str, Any]) -> OnvifEvent:
    topic = _extract_topic(message.get("Topic"))
    utc_time = None
    property_operation = None
    source: dict[str, str] = {}
    data: dict[str, str] = {}

    message_node = message.get("Message")
    root = _coerce_message_root(message_node)
    if root is not None:
        utc_time = _parse_datetime(root.attrib.get("UtcTime"))
        property_operation = root.attrib.get("PropertyOperation")
        source = _extract_simple_items(root.find("tt:Source", NS))
        data = _extract_simple_items(root.find("tt:Data", NS))
    elif isinstance(message_node, dict):
        utc_time = _parse_datetime(message_node.get("UtcTime"))
        property_operation = message_node.get("PropertyOperation")
        source = _coerce_simple_items(message_node.get("Source"))
        data = _coerce_simple_items(message_node.get("Data"))

    return OnvifEvent(
        topic=topic or "",
        utc_time=utc_time,
        property_operation=property_operation,
        source=source,
        data=data,
        raw=message,
    )


def decide_trigger(event: OnvifEvent) -> TriggerDecision:
    if _is_true(event.data.get("IsPet")):
        return TriggerDecision(True, "pet", "animal event")
    if _is_true(event.data.get("IsMotion")):
        return TriggerDecision(True, "motion", "general motion event")
    return TriggerDecision(False, None, None)


def summarize_event(event: OnvifEvent) -> dict[str, Any]:
    return {
        "topic": event.topic,
        "utc_time": event.utc_time.isoformat() if event.utc_time else None,
        "property_operation": event.property_operation,
        "source": event.source,
        "data": event.data,
    }


def _extract_simple_items(node: ElementTree.Element | None) -> dict[str, str]:
    if node is None:
        return {}
    items: dict[str, str] = {}
    for child in node.findall("tt:SimpleItem", NS):
        name = child.attrib.get("Name")
        value = child.attrib.get("Value")
        if name and value is not None:
            items[name] = value
    return items


def _extract_topic(topic_node: Any) -> str | None:
    if isinstance(topic_node, dict):
        value = topic_node.get("_value_1")
        return str(value) if value is not None else None
    if topic_node is not None:
        return str(topic_node)
    return None


def _extract_message_xml(message_node: Any) -> str | None:
    if isinstance(message_node, dict):
        value = message_node.get("_value_1")
        return _coerce_xml_text(value)
    if message_node is not None:
        return _coerce_xml_text(message_node)
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _is_true(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"true", "1", "on", "yes"}


def _coerce_message_root(message_node: Any) -> ElementTree.Element | None:
    xml_payload = _extract_message_xml(message_node)
    if not xml_payload:
        return None

    xml_payload = xml_payload.strip()
    start = xml_payload.find("<")
    if start > 0:
        xml_payload = xml_payload[start:]

    try:
        return ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None


def _coerce_xml_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "tag") and hasattr(value, "attrib"):
        try:
            return tostring(value, encoding="unicode")
        except Exception:
            return None
    return str(value)


def _coerce_simple_items(node: Any) -> dict[str, str]:
    if isinstance(node, dict):
        simple_items = node.get("SimpleItem")
        if isinstance(simple_items, dict):
            simple_items = [simple_items]
        if isinstance(simple_items, list):
            items: dict[str, str] = {}
            for child in simple_items:
                if not isinstance(child, dict):
                    continue
                name = child.get("Name")
                value = child.get("Value")
                if name and value is not None:
                    items[str(name)] = str(value)
            return items
    return {}
