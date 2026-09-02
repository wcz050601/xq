from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import Callable

from websockets.asyncio.server import serve

import server


def local_ip() -> str:
    """Return the most useful LAN address without sending any network traffic."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        probe.close()


class EmbeddedServer:
    def __init__(self):
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop_flag = threading.Event()

    def start(self, port: int, on_ready: Callable[[], None], on_error: Callable[[str], None]) -> None:
        self.stop()
        self.stop_flag = threading.Event()
        self.thread = threading.Thread(
            target=self._thread_main, args=(port, on_ready, on_error), daemon=True
        )
        self.thread.start()

    def _thread_main(self, port: int, on_ready, on_error) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run(port, on_ready))
        except Exception as exc:
            on_error(str(exc))
        finally:
            self.loop.close()
            self.loop = None

    async def _run(self, port: int, on_ready) -> None:
        server.ROOMS.clear()
        server.CONNECTIONS.clear()
        async with serve(server.connection, "0.0.0.0", port, ping_interval=20, ping_timeout=20):
            ticker = asyncio.create_task(server.ticker())
            on_ready()
            try:
                while not self.stop_flag.is_set():
                    await asyncio.sleep(.2)
            finally:
                ticker.cancel()
                try:
                    await ticker
                except asyncio.CancelledError:
                    pass

    def stop(self) -> None:
        self.stop_flag.set()
        if self.loop:
            self.loop.call_soon_threadsafe(lambda: None)
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        self.thread = None

