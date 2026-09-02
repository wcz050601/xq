import asyncio
import json
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

import server


async def receive_type(websocket, wanted="state"):
    for _ in range(5):
        message = json.loads(await asyncio.wait_for(websocket.recv(), 2))
        if message.get("type") == wanted:
            return message
    raise AssertionError(f"未收到 {wanted} 消息")


class ServerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        server.ROOMS.clear()
        server.CONNECTIONS.clear()
        self.listener = await serve(server.connection, "127.0.0.1", 0)
        port = self.listener.sockets[0].getsockname()[1]
        self.url = f"ws://127.0.0.1:{port}"

    async def asyncTearDown(self):
        self.listener.close()
        await self.listener.wait_closed()
        server.ROOMS.clear()
        server.CONNECTIONS.clear()

    async def test_create_join_move_and_approved_undo(self):
        async with connect(self.url) as red, connect(self.url) as black:
            await red.send(json.dumps({
                "action": "create", "room": "integration",
                "total_seconds": 600, "move_seconds": 60, "handicap": [],
            }))
            joined_red = await receive_type(red, "joined")
            self.assertEqual(joined_red["color"], "red")
            await receive_type(red)

            await black.send(json.dumps({"action": "join", "room": "integration"}))
            joined_black = await receive_type(black, "joined")
            self.assertEqual(joined_black["color"], "black")
            self.assertTrue((await receive_type(red))["started"])
            self.assertTrue((await receive_type(black))["started"])

            move = {"src": [6, 0], "dst": [5, 0]}
            await red.send(json.dumps({"action": "move", "move": move}))
            red_state = await receive_type(red)
            black_state = await receive_type(black)
            self.assertEqual(red_state["game"]["turn"], "black")
            self.assertEqual(black_state["game"]["board"][5][0], "P")
            self.assertEqual(black_state["moves"], [move])

            await red.send(json.dumps({"action": "undo_request"}))
            self.assertEqual((await receive_type(black))["pending_undo"], "red")
            await receive_type(red)
            await black.send(json.dumps({"action": "undo_answer", "accept": True}))
            restored = await receive_type(red)
            await receive_type(black)
            self.assertEqual(restored["undo_result"], "accepted")
            self.assertEqual(restored["game"]["board"][6][0], "P")
            self.assertEqual(restored["game"]["turn"], "red")

            await red.send(json.dumps({"action": "chat", "text": "你好", "kind": "text"}))
            red_chat = await receive_type(red, "chat")
            black_chat = await receive_type(black, "chat")
            self.assertEqual(red_chat["message"]["text"], "你好")
            self.assertEqual(black_chat["message"]["color"], "red")


if __name__ == "__main__":
    unittest.main()
