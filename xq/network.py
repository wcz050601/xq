from __future__ import annotations

import asyncio
import json
import ssl
import threading
from collections.abc import Callable

from websockets.asyncio.client import connect


class NetworkClient:
    """Async WebSocket client hosted in a background thread for Kivy."""

    def __init__(self, on_message: Callable[[dict], None], on_error: Callable[[str], None]):
        self.on_message = on_message
        self.on_error = on_error
        self.loop: asyncio.AbstractEventLoop | None = None
        self.websocket = None
        self.thread: threading.Thread | None = None

    def start(self, url: str, first_message: dict) -> None:
        self.close()
        self.thread = threading.Thread(target=self._thread_main, args=(url, first_message), daemon=True)
        self.thread.start()

    def _thread_main(self, url: str, first_message: dict) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run(url, first_message))
        except Exception as exc:
            self.on_error(str(exc))
        finally:
            self.websocket = None
            self.loop.close()
            self.loop = None

    async def _run(self, url: str, first_message: dict) -> None:
        options = {}
        if url.startswith("wss://"):
            import certifi
            options["ssl"] = ssl.create_default_context(cafile=certifi.where())
        async with connect(url, ping_interval=20, ping_timeout=20, **options) as websocket:
            self.websocket = websocket
            await websocket.send(json.dumps(first_message, ensure_ascii=False))
            async for raw in websocket:
                self.on_message(json.loads(raw))

    def send(self, message: dict) -> None:
        if not self.loop or not self.websocket:
            self.on_error("尚未连接服务器")
            return
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send(json.dumps(message, ensure_ascii=False)), self.loop
        )
        future.add_done_callback(lambda f: self.on_error(str(f.exception())) if f.exception() else None)

    def close(self) -> None:
        if self.loop and self.websocket:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
