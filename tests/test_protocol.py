import unittest
from unittest.mock import patch

from xq.game import BLACK, RED, Move
from xq.protocol import Room


class RoomTests(unittest.TestCase):
    def test_two_players_start_room(self):
        room = Room("abc", total_seconds=600, move_seconds=30)
        self.assertEqual(room.add_player(object()), RED)
        self.assertFalse(room.started)
        self.assertEqual(room.add_player(object()), BLACK)
        self.assertTrue(room.started)
        with self.assertRaisesRegex(ValueError, "房间已满"):
            room.add_player(object())

    def test_turn_is_enforced(self):
        room = Room("abc")
        room.add_player(object())
        room.add_player(object())
        with self.assertRaisesRegex(ValueError, "还没轮到你"):
            room.move(BLACK, Move((3, 0), (4, 0)))

    def test_undo_requires_opponent_and_restores_move(self):
        room = Room("abc", total_seconds=600)
        room.add_player(object())
        room.add_player(object())
        room.move(RED, Move((6, 0), (5, 0)))
        self.assertEqual(room.state()["moves"], [{"src": [6, 0], "dst": [5, 0]}])
        room.request_undo(RED)
        with self.assertRaisesRegex(ValueError, "必须由对方"):
            room.answer_undo(RED, True)
        self.assertTrue(room.answer_undo(BLACK, True))
        self.assertEqual(room.game.piece_at((6, 0)), "P")
        self.assertEqual(room.game.turn, RED)
        self.assertEqual(room.state()["moves"], [])

    def test_rejected_undo_keeps_board(self):
        room = Room("abc")
        room.add_player(object())
        room.add_player(object())
        room.move(RED, Move((6, 0), (5, 0)))
        room.request_undo(RED)
        self.assertFalse(room.answer_undo(BLACK, False))
        self.assertEqual(room.game.piece_at((5, 0)), "P")

    def test_chat_text_and_emoji_are_kept_in_room(self):
        room = Room("abc")
        room.add_player(object())
        message = room.add_chat(RED, "你好")
        emoji = room.add_chat(BLACK, "👍", "emoji")
        self.assertEqual(message["id"], 1)
        self.assertEqual(emoji["kind"], "emoji")
        self.assertEqual(room.state()["chat"], [message, emoji])
        with self.assertRaisesRegex(ValueError, "不能为空"):
            room.add_chat(RED, "   ")
        with self.assertRaisesRegex(ValueError, "200"):
            room.add_chat(RED, "x" * 201)

    @patch("xq.protocol.time.monotonic")
    def test_move_timeout(self, monotonic):
        monotonic.return_value = 100
        room = Room("abc", move_seconds=10)
        room.add_player(object())
        room.add_player(object())
        room.turn_started = 100
        monotonic.return_value = 111
        self.assertTrue(room.check_timeout())
        self.assertEqual(room.game.winner, BLACK)
        self.assertEqual(room.game.reason, "步时超时")


if __name__ == "__main__":
    unittest.main()
