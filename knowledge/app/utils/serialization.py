"""
Serialization helpers for LangGraph state and msgpack-safe values.

Converts numpy and other non-JSON-serializable types to native Python types
so checkpoint serialization (msgpack) does not fail.
"""
from typing import Any


def to_native_types(obj: Any) -> Any:
    """
    Recursively convert numpy scalars and arrays to native Python types.
    Ensures dicts/lists stored in graph state are msgpack-serializable.
    """
    if obj is None:
        return None
    try:
        import numpy as np
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [to_native_types(x) for x in obj.tolist()]
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: to_native_types(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native_types(x) for x in obj]
    return obj
