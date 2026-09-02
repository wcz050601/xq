from __future__ import annotations

import time
from dataclasses import dataclass, field

from .game import BLACK, RED, Game, Move, opponent


@dataclass
class Player:
    websocket: object
    color: str


@dataclass
class Room:
    code: str
    total_seconds: int = 0
    move_seconds: int = 0
    handicap: list[str] = field(default_factory=list)
    game: Game = field(init=False)
    players: dict[str, Player] = field(default_factory=dict)
    clocks: dict[str, float] = field(init=False)
    turn_started: float = field(default_factory=time.monotonic)
    started: bool = False
    pending_undo: str | None = None
    clock_history: list[dict] = field(default_factory=list)
    move_log: list[dict] = field(default_factory=list)
    chat_log: list[dict] = field(default_factory=list)
    chat_seq: int = 0

    def __post_init__(self):
        self.game = Game(self.handicap)
        self.clocks = {RED: float(self.total_seconds), BLACK: float(self.total_seconds)}

    def add_player(self, websocket) -> str:
        if RED not in self.players:
            color = RED
        elif BLACK not in self.players:
            color = BLACK
        else:
            raise ValueError("房间已满")
        self.players[color] = Player(websocket, color)
        if len(self.players) == 2:
            self.started = True
            self.turn_started = time.monotonic()
        return color

    def effective_clocks(self, now: float | None = None) -> dict[str, float]:
        values = self.clocks.copy()
        if self.started and not self.game.winner and self.total_seconds > 0:
            elapsed = (now or time.monotonic()) - self.turn_started
            values[self.game.turn] = max(0.0, values[self.game.turn] - elapsed)
        return values

    def state(self) -> dict:
        clocks = self.effective_clocks()
        remaining_move = 0.0
        if self.move_seconds > 0 and self.started and not self.game.winner:
            remaining_move = max(0.0, self.move_seconds - (time.monotonic() - self.turn_started))
        return {
            "type": "state", "room": self.code, "game": self.game.serialize(),
            "clocks": clocks, "move_remaining": remaining_move,
            "started": self.started, "pending_undo": self.pending_undo,
            "moves": list(self.move_log),
            "chat": list(self.chat_log),
            "settings": {"total_seconds": self.total_seconds, "move_seconds": self.move_seconds, "handicap": self.handicap},
        }

    def check_timeout(self) -> bool:
        if not self.started or self.game.winner:
            return False
        elapsed = time.monotonic() - self.turn_started
        total_expired = self.total_seconds > 0 and self.clocks[self.game.turn] - elapsed <= 0
        move_expired = self.move_seconds > 0 and elapsed >= self.move_seconds
        if total_expired or move_expired:
            self.game.winner = opponent(self.game.turn)
            self.game.reason = "局时超时" if total_expired else "步时超时"
            if total_expired:
                self.clocks[self.game.turn] = 0
            return True
        return False

    def move(self, color: str, move: Move) -> dict:
        if not self.started:
            raise ValueError("等待对手加入")
        self.check_timeout()
        if self.game.winner:
            raise ValueError("对局已经结束")
        if color != self.game.turn:
            raise ValueError("还没轮到你")
        elapsed = time.monotonic() - self.turn_started
        if self.move_seconds > 0 and elapsed >= self.move_seconds:
            self.check_timeout()
            raise ValueError("步时已用完")
        before = self.clocks.copy()
        if self.total_seconds > 0:
            self.clocks[color] = max(0.0, self.clocks[color] - elapsed)
        result = self.game.make_move(move)
        self.move_log.append(move.to_dict())
        self.clock_history.append(before)
        self.turn_started = time.monotonic()
        self.pending_undo = None
        return result

    def request_undo(self, color: str) -> None:
        if not self.game.history:
            raise ValueError("没有可以悔棋的步骤")
        if self.pending_undo:
            raise ValueError("已有待处理的悔棋请求")
        self.pending_undo = color

    def add_chat(self, color: str, text: str, kind: str = "text") -> dict:
        text = str(text).strip()
        if not text:
            raise ValueError("消息不能为空")
        if len(text) > 200:
            raise ValueError("消息不能超过 200 个字符")
        if kind not in ("text", "emoji"):
            raise ValueError("不支持的消息类型")
        self.chat_seq += 1
        entry = {
            "id": self.chat_seq, "color": color, "text": text,
            "kind": kind, "time": int(time.time()),
        }
        self.chat_log.append(entry)
        self.chat_log = self.chat_log[-100:]
        return entry

    def answer_undo(self, color: str, accept: bool) -> bool:
        if not self.pending_undo:
            raise ValueError("没有待处理的悔棋请求")
        if color == self.pending_undo:
            raise ValueError("必须由对方处理悔棋请求")
        changed = False
        if accept:
            changed = self.game.undo()
            if changed and self.clock_history:
                self.clocks = self.clock_history.pop()
            if changed and self.move_log:
                self.move_log.pop()
            self.turn_started = time.monotonic()
        self.pending_undo = None
        return changed
