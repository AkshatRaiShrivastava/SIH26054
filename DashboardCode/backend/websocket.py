"""WebSocket broadcast utilities for telemetry clients."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Set

from fastapi import WebSocket

from .models import EngineTelemetry


@dataclass
class TelemetryBroadcaster:
    subscribers: Set[asyncio.Queue] = field(default_factory=set)

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)

    async def broadcast(self, telemetry: EngineTelemetry) -> None:
        stale = []
        for queue in self.subscribers:
            try:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(telemetry)
            except Exception:
                stale.append(queue)
        for queue in stale:
            self.subscribers.discard(queue)


async def websocket_telemetry_endpoint(websocket: WebSocket, broadcaster: TelemetryBroadcaster) -> None:
    await websocket.accept()
    queue = await broadcaster.subscribe()
    try:
        while True:
            telemetry = await queue.get()
            await websocket.send_json(telemetry.model_dump(mode="json"))
    finally:
        broadcaster.unsubscribe(queue)
