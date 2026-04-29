import threading
from typing import Any, Dict, Optional

_runtime_lock = threading.Lock()
_runtime_registry: Dict[str, Dict[str, Any]] = {}


def register_runtime(request_id: str, payload: Optional[Dict[str, Any]] = None):
    with _runtime_lock:
        _runtime_registry[request_id] = {
            'cancelled': False,
            'payload': payload or {},
        }


def cancel_runtime(request_id: str) -> bool:
    with _runtime_lock:
        data = _runtime_registry.get(request_id)
        if not data:
            return False
        data['cancelled'] = True
        return True


def is_cancelled(request_id: str) -> bool:
    with _runtime_lock:
        data = _runtime_registry.get(request_id)
        return bool(data and data.get('cancelled'))


def cleanup_runtime(request_id: str):
    with _runtime_lock:
        _runtime_registry.pop(request_id, None)
