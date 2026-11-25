"""In-process dispatch producer, retry transport and consumer for the fixture."""
from collections import deque
import json


def accept(request_id):
    if not request_id.strip():
        raise ValueError("A request ID is required")
    return json.dumps({"request_id": request_id})


def deliver(message, copies):
    return deque(message for _ in range(copies))


def consume(inbox, entries, enqueue):
    received = []
    while inbox:
        request = json.loads(inbox.popleft())["request_id"]
        enqueue(entries, request)
        received.append(request)
    return received
