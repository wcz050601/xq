import asyncio
import json
import socket
import threading
import unittest

from websockets.asyncio.client import connect

from xq.embedded_server import EmbeddedServer


class EmbeddedServerTests(unittest.TestCase):
    def test_server_starts_inside_process_and_accepts_room(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        ready, errors = threading.Event(), []
        hosted = EmbeddedServer()
        hosted.start(port, ready.set, errors.append)
        self.assertTrue(ready.wait(3), errors)

        async def create_room():
            async with connect(f"ws://127.0.0.1:{port}") as websocket:
                await websocket.send(json.dumps({
                    "action": "create", "room": "inside_app",
                    "total_seconds": 300, "move_seconds": 30, "handicap": [],
                }))
                joined = json.loads(await asyncio.wait_for(websocket.recv(), 2))
                state = json.loads(await asyncio.wait_for(websocket.recv(), 2))
                return joined, state

        try:
            joined, state = asyncio.run(create_room())
            self.assertEqual(joined["type"], "joined")
            self.assertEqual(state["room"], "inside_app")
        finally:
            hosted.stop()
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
