import asyncio
from typing import Dict, Tuple, List, Any

# Keyed by (user_id, session_id)
subscribers: Dict[Tuple[str, str], List[asyncio.Queue]] = {}

def publish_update(user_id: str, session_id: str, data: Any):
    key = (user_id, session_id)
    if key in subscribers:
        for queue in subscribers[key]:
            queue.put_nowait(data)

def add_subscriber(user_id: str, session_id: str, queue: asyncio.Queue):
    key = (user_id, session_id)
    if key not in subscribers:
        subscribers[key] = []
    subscribers[key].append(queue)

def remove_subscriber(user_id: str, session_id: str, queue: asyncio.Queue):
    key = (user_id, session_id)
    if key in subscribers:
        subscribers[key].remove(queue)
        if not subscribers[key]:
            del subscribers[key] 