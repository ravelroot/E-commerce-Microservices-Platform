import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator
from typing import Protocol

log = logging.getLogger("argo.events")

STOCK_CHANNEL = "argo:stock"


class EventBus(Protocol):
    def publish(self, channel: str, payload: dict) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict]: ...


class MemoryEventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}
        self._lock = threading.Lock()
        self.published: list[tuple[str, dict]] = []

    def publish(self, channel: str, payload: dict) -> None:
        self.published.append((channel, payload))
        with self._lock:
            subs = list(self._subs.get(channel, []))
        for loop, queue in subs:
            loop.call_soon_threadsafe(queue.put_nowait, payload)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue()
        entry = (asyncio.get_running_loop(), queue)
        with self._lock:
            self._subs.setdefault(channel, []).append(entry)
        try:
            while True:
                yield await queue.get()
        finally:
            with self._lock:
                self._subs[channel].remove(entry)


class RedisEventBus:
    def __init__(self, url: str) -> None:
        import redis
        import redis.asyncio as aioredis

        self._sync = redis.Redis.from_url(url)
        self._url = url
        self._aioredis = aioredis

    def publish(self, channel: str, payload: dict) -> None:
        try:
            self._sync.publish(channel, json.dumps(payload))
        except Exception as exc:
            log.warning("não foi possível publicar evento: %s", exc)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        client = self._aioredis.Redis.from_url(self._url)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await client.aclose()


def build_event_bus(redis_url: str, environment: str) -> EventBus:
    if environment == "test" or not redis_url:
        return MemoryEventBus()
    return RedisEventBus(redis_url)


_bus: EventBus | None = None
_bus_lock = threading.Lock()


def get_bus() -> EventBus:
    """Barramento do processo: Redis em produção, memória nos testes."""
    global _bus
    with _bus_lock:
        if _bus is None:
            from django.conf import settings

            _bus = build_event_bus(settings.ARGO_REDIS_URL, settings.ARGO_ENVIRONMENT)
        return _bus


def set_bus(bus: EventBus | None) -> None:
    global _bus
    with _bus_lock:
        _bus = bus
