from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from xq.game import Move
from xq.protocol import Room


ROOM_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
ROOMS: dict[str, Room] = {}
CONNECTIONS: dict[object, tuple[str, str]] = {}


async def send(ws, payload: dict) -> None:
    await ws.send(json.dumps(payload, ensure_ascii=False))


async def broadcast(room: Room, payload: dict | None = None) -> None:
    message = json.dumps(payload or room.state(), ensure_ascii=False)
    stale = []
    for player in room.players.values():
        try:
            await player.websocket.send(message)
        except ConnectionClosed:
            stale.append(player.color)
    for color in stale:
        room.players.pop(color, None)


def parse_settings(message: dict) -> tuple[int, int, list[str]]:
    total = max(0, min(int(message.get("total_seconds", 0)), 24 * 3600))
    per_move = max(0, min(int(message.get("move_seconds", 0)), 3600))
    handicap = message.get("handicap", [])
    if not isinstance(handicap, list):
        raise ValueError("让子设置格式错误")
    return total, per_move, [str(item).strip() for item in handicap]


async def handle_message(ws, message: dict) -> None:
    action = message.get("action")
    if action in ("create", "join"):
        if ws in CONNECTIONS:
            raise ValueError("已经加入房间")
        code = str(message.get("room", "")).strip()
        if not ROOM_RE.fullmatch(code):
            raise ValueError("房间号只能包含 1-20 个字母、数字、下划线或短横线")
        if action == "create":
            if code in ROOMS:
                raise ValueError("房间号已存在")
            total, per_move, handicap = parse_settings(message)
            ROOMS[code] = Room(code, total, per_move, handicap)
        elif code not in ROOMS:
            raise ValueError("房间不存在")
        room = ROOMS[code]
        color = room.add_player(ws)
        CONNECTIONS[ws] = (code, color)
        await send(ws, {"type": "joined", "room": code, "color": color})
        await broadcast(room)
        return

    if ws not in CONNECTIONS:
        raise ValueError("请先创建或加入房间")
    code, color = CONNECTIONS[ws]
    room = ROOMS[code]
    if action == "move":
        result = room.move(color, Move.from_dict(message["move"]))
        await broadcast(room, {**room.state(), "last_move": message["move"], "captured": result["captured"]})
    elif action == "undo_request":
        room.request_undo(color)
        await broadcast(room)
    elif action == "undo_answer":
        accepted = bool(message.get("accept", False))
        changed = room.answer_undo(color, accepted)
        await broadcast(room, {**room.state(), "undo_result": "accepted" if changed else "rejected"})
    elif action == "chat":
        entry = room.add_chat(color, message.get("text", ""), message.get("kind", "text"))
        await broadcast(room, {"type": "chat", "message": entry})
    elif action == "ping":
        await send(ws, {"type": "pong"})
    else:
        raise ValueError("未知操作")


async def connection(ws) -> None:
    try:
        async for raw in ws:
            try:
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError("消息格式错误")
                await handle_message(ws, message)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                await send(ws, {"type": "error", "message": str(exc)})
    except ConnectionClosed:
        pass
    finally:
        info = CONNECTIONS.pop(ws, None)
        if info:
            code, color = info
            room = ROOMS.get(code)
            if room:
                room.players.pop(color, None)
                room.started = False
                room.pending_undo = None
                if room.players:
                    await broadcast(room, {**room.state(), "notice": "对手已离线"})
                else:
                    ROOMS.pop(code, None)


async def ticker() -> None:
    while True:
        await asyncio.sleep(1)
        for room in list(ROOMS.values()):
            changed = room.check_timeout()
            if room.started:
                await broadcast(room)
            if changed:
                logging.info("room %s ended: %s", room.code, room.game.reason)


async def run(host: str, port: int) -> None:
    logging.info("Chinese chess server listening on ws://%s:%s", host, port)
    async with serve(connection, host, port, ping_interval=20, ping_timeout=20):
        await ticker()


def main() -> None:
    parser = argparse.ArgumentParser(description="Python 中国象棋 WebSocket 服务端")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
