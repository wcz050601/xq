from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


RED = "red"
BLACK = "black"
ROWS = 10
COLS = 9


@dataclass(frozen=True)
class Move:
    src: tuple[int, int]
    dst: tuple[int, int]

    def to_dict(self) -> dict:
        return {"src": list(self.src), "dst": list(self.dst)}

    @classmethod
    def from_dict(cls, value: dict) -> "Move":
        return cls(tuple(value["src"]), tuple(value["dst"]))


STARTING_BOARD = (
    "rheakaehr",
    ".........",
    ".c.....c.",
    "p.p.p.p.p",
    ".........",
    ".........",
    "P.P.P.P.P",
    ".C.....C.",
    ".........",
    "RHEAKAEHR",
)

HANDICAP_SQUARES = {
    "r1": (0, 0), "h1": (0, 1), "e1": (0, 2), "a1": (0, 3),
    "a2": (0, 5), "e2": (0, 6), "h2": (0, 7), "r2": (0, 8),
    "c1": (2, 1), "c2": (2, 7),
    "p1": (3, 0), "p2": (3, 2), "p3": (3, 4), "p4": (3, 6), "p5": (3, 8),
    "R1": (9, 0), "H1": (9, 1), "E1": (9, 2), "A1": (9, 3),
    "A2": (9, 5), "E2": (9, 6), "H2": (9, 7), "R2": (9, 8),
    "C1": (7, 1), "C2": (7, 7),
    "P1": (6, 0), "P2": (6, 2), "P3": (6, 4), "P4": (6, 6), "P5": (6, 8),
}


def color_of(piece: str) -> Optional[str]:
    if piece == ".":
        return None
    return RED if piece.isupper() else BLACK


def opponent(color: str) -> str:
    return BLACK if color == RED else RED


class Game:
    def __init__(self, handicap: Iterable[str] = ()):
        self.board = [list(row) for row in STARTING_BOARD]
        for token in handicap:
            token = token.strip()
            square = HANDICAP_SQUARES.get(token)
            if square:
                r, c = square
                self.board[r][c] = "."
        self.turn = RED
        self.winner: Optional[str] = None
        self.reason = ""
        self.history: list[dict] = []

    def clone_board(self) -> list[list[str]]:
        return [row[:] for row in self.board]

    def serialize(self) -> dict:
        return {
            "board": ["".join(row) for row in self.board],
            "turn": self.turn,
            "winner": self.winner,
            "reason": self.reason,
            "move_count": len(self.history),
        }

    @classmethod
    def from_state(cls, state: dict) -> "Game":
        game = cls()
        game.board = [list(row) for row in state["board"]]
        game.turn = state.get("turn", RED)
        game.winner = state.get("winner")
        game.reason = state.get("reason", "")
        return game

    def piece_at(self, pos: tuple[int, int]) -> str:
        r, c = pos
        return self.board[r][c]

    @staticmethod
    def inside(pos: tuple[int, int]) -> bool:
        r, c = pos
        return 0 <= r < ROWS and 0 <= c < COLS

    def pseudo_legal(self, move: Move) -> bool:
        if not self.inside(move.src) or not self.inside(move.dst) or move.src == move.dst:
            return False
        sr, sc = move.src
        dr, dc = move.dst
        piece = self.board[sr][sc]
        target = self.board[dr][dc]
        color = color_of(piece)
        if color is None or color == color_of(target):
            return False
        kind = piece.lower()
        rr, cc = dr - sr, dc - sc

        if kind == "r":
            return (sr == dr or sc == dc) and self._screens(move) == 0
        if kind == "c":
            screens = self._screens(move)
            return (target == "." and screens == 0) or (target != "." and screens == 1)
        if kind == "h":
            if (abs(rr), abs(cc)) not in ((2, 1), (1, 2)):
                return False
            leg = (sr + (rr // 2 if abs(rr) == 2 else 0), sc + (cc // 2 if abs(cc) == 2 else 0))
            return self.piece_at(leg) == "."
        if kind == "e":
            if abs(rr) != 2 or abs(cc) != 2:
                return False
            if color == RED and dr < 5 or color == BLACK and dr > 4:
                return False
            return self.board[sr + rr // 2][sc + cc // 2] == "."
        if kind == "a":
            return abs(rr) == 1 and abs(cc) == 1 and self._in_palace(color, dr, dc)
        if kind == "k":
            if target.lower() == "k" and sc == dc and self._screens(move) == 0:
                return True
            return abs(rr) + abs(cc) == 1 and self._in_palace(color, dr, dc)
        if kind == "p":
            forward = -1 if color == RED else 1
            crossed = sr <= 4 if color == RED else sr >= 5
            return (rr == forward and cc == 0) or (crossed and rr == 0 and abs(cc) == 1)
        return False

    def is_legal(self, move: Move, color: Optional[str] = None) -> bool:
        color = color or self.turn
        if self.winner or color_of(self.piece_at(move.src)) != color or not self.pseudo_legal(move):
            return False
        captured = self._apply_raw(move)
        legal = not self.in_check(color)
        self._undo_raw(move, captured)
        return legal

    def legal_moves(self, color: Optional[str] = None):
        color = color or self.turn
        for sr in range(ROWS):
            for sc in range(COLS):
                if color_of(self.board[sr][sc]) != color:
                    continue
                for dr in range(ROWS):
                    for dc in range(COLS):
                        move = Move((sr, sc), (dr, dc))
                        if self.is_legal(move, color):
                            yield move

    def make_move(self, move: Move) -> dict:
        if not self.is_legal(move):
            raise ValueError("非法走子")
        snapshot = {
            "board": self.clone_board(), "turn": self.turn,
            "winner": self.winner, "reason": self.reason,
        }
        captured = self._apply_raw(move)
        mover = self.turn
        self.turn = opponent(self.turn)
        self.history.append(snapshot)
        if captured.lower() == "k":
            self.winner, self.reason = mover, "将帅被吃"
        elif not any(self.legal_moves(self.turn)):
            self.winner = mover
            self.reason = "将死" if self.in_check(self.turn) else "困毙"
        return {"captured": captured != ".", "piece": self.piece_at(move.dst)}

    def undo(self) -> bool:
        if not self.history:
            return False
        state = self.history.pop()
        self.board = [row[:] for row in state["board"]]
        self.turn = state["turn"]
        self.winner = state["winner"]
        self.reason = state["reason"]
        return True

    def in_check(self, color: str) -> bool:
        king = "K" if color == RED else "k"
        king_pos = next(((r, c) for r in range(ROWS) for c in range(COLS) if self.board[r][c] == king), None)
        if king_pos is None:
            return True
        foe = opponent(color)
        for r in range(ROWS):
            for c in range(COLS):
                if color_of(self.board[r][c]) == foe and self.pseudo_legal(Move((r, c), king_pos)):
                    return True
        return False

    def _apply_raw(self, move: Move) -> str:
        sr, sc = move.src
        dr, dc = move.dst
        captured = self.board[dr][dc]
        self.board[dr][dc] = self.board[sr][sc]
        self.board[sr][sc] = "."
        return captured

    def _undo_raw(self, move: Move, captured: str) -> None:
        sr, sc = move.src
        dr, dc = move.dst
        self.board[sr][sc] = self.board[dr][dc]
        self.board[dr][dc] = captured

    def _screens(self, move: Move) -> int:
        sr, sc = move.src
        dr, dc = move.dst
        if sr != dr and sc != dc:
            return -1
        step_r = 0 if sr == dr else (1 if dr > sr else -1)
        step_c = 0 if sc == dc else (1 if dc > sc else -1)
        r, c = sr + step_r, sc + step_c
        count = 0
        while (r, c) != (dr, dc):
            count += self.board[r][c] != "."
            r, c = r + step_r, c + step_c
        return count

    @staticmethod
    def _in_palace(color: str, row: int, col: int) -> bool:
        return 3 <= col <= 5 and ((7 <= row <= 9) if color == RED else (0 <= row <= 2))

