import time
from typing import Any, Dict, List, Optional, Set

_subscribers: Dict[str, Set[str]] = {}
_history: Dict[str, List[Dict[str, Any]]] = {}

MAX_BUFFER_SIZE = 50


def storage_subscribe(feature: str, chat_id: str) -> None:
    _subscribers.setdefault(feature, set()).add(chat_id)


def storage_unsubscribe(feature: str, chat_id: str) -> None:
    if feature in _subscribers:
        _subscribers[feature].discard(chat_id)


def storage_is_enabled(chat_id: str) -> bool:
    return any(chat_id in s for s in _subscribers.values())


def storage_capture(chat_id: str, sender: str, text: str, message_id: str, timestamp: Optional[float] = None) -> None:
    if not storage_is_enabled(chat_id):
        return
    buf = _history.setdefault(chat_id, [])
    buf.append({
        "sender": sender,
        "text": text,
        "message_id": message_id,
        "timestamp": timestamp or time.time(),
    })
    buf[:] = buf[-MAX_BUFFER_SIZE:]


def storage_get_messages(chat_id: str, n: int = 20) -> List[Dict[str, Any]]:
    return _history.get(chat_id, [])[-n:]


def storage_get_length(chat_id: str) -> int:
    return len(_history.get(chat_id, []))


def storage_get_since(chat_id: str, index: int) -> List[Dict[str, Any]]:
    buf = _history.get(chat_id, [])
    if index >= len(buf):
        return []
    return buf[index:]
