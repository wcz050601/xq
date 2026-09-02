import unittest

from xq.game import BLACK, RED, Game, Move


class GameRulesTests(unittest.TestCase):
    def test_starting_position_and_turn(self):
        game = Game()
        self.assertEqual(game.turn, RED)
        self.assertEqual(game.piece_at((9, 4)), "K")
        self.assertEqual(game.piece_at((0, 4)), "k")

    def test_pawn_moves_forward_and_not_backward(self):
        game = Game()
        self.assertTrue(game.is_legal(Move((6, 0), (5, 0))))
        self.assertFalse(game.is_legal(Move((6, 0), (7, 0))))
        self.assertFalse(game.is_legal(Move((6, 0), (6, 1))))

    def test_pawn_can_move_sideways_after_crossing_river(self):
        game = Game()
        game.board[6][0] = "."
        game.board[4][0] = "P"
        self.assertTrue(game.is_legal(Move((4, 0), (4, 1))))
        self.assertFalse(game.is_legal(Move((4, 0), (5, 0))))

    def test_horse_leg_can_be_blocked(self):
        game = Game()
        self.assertTrue(game.is_legal(Move((9, 1), (7, 2))))
        game.board[8][1] = "P"
        self.assertFalse(game.is_legal(Move((9, 1), (7, 2))))

    def test_elephant_cannot_cross_river(self):
        game = Game()
        game.board = [list(".........") for _ in range(10)]
        game.board[9][4], game.board[0][3] = "K", "k"
        game.board[7][2] = "E"
        self.assertTrue(game.pseudo_legal(Move((7, 2), (5, 4))))
        game.board[5][4] = "E"
        game.board[7][2] = "."
        self.assertFalse(game.pseudo_legal(Move((5, 4), (3, 6))))

    def test_cannon_needs_exactly_one_screen_to_capture(self):
        game = Game()
        game.board = [list(".........") for _ in range(10)]
        game.board[7][1], game.board[0][1] = "C", "r"
        self.assertFalse(game.pseudo_legal(Move((7, 1), (0, 1))))
        game.board[3][1] = "p"
        self.assertTrue(game.pseudo_legal(Move((7, 1), (0, 1))))

    def test_flying_generals_make_exposing_move_illegal(self):
        game = Game()
        game.board = [list(".........") for _ in range(10)]
        game.board[0][4], game.board[9][4], game.board[5][4] = "k", "K", "R"
        self.assertFalse(game.is_legal(Move((5, 4), (5, 5)), RED))

    def test_cannot_ignore_check(self):
        game = Game()
        game.board = [list(".........") for _ in range(10)]
        game.board[0][4], game.board[9][4] = "k", "K"
        game.board[5][4], game.board[9][0] = "r", "R"
        self.assertFalse(game.is_legal(Move((9, 0), (8, 0)), RED))
        self.assertTrue(game.is_legal(Move((9, 4), (9, 3)), RED))

    def test_move_and_unlimited_undo_history(self):
        game = Game()
        original = game.serialize()["board"]
        game.make_move(Move((6, 0), (5, 0)))
        game.make_move(Move((3, 0), (4, 0)))
        self.assertTrue(game.undo())
        self.assertTrue(game.undo())
        self.assertFalse(game.undo())
        self.assertEqual(game.serialize()["board"], original)
        self.assertEqual(game.turn, RED)

    def test_handicap_removes_requested_pieces_only(self):
        game = Game(["R1", "h2", "K", "unknown"])
        self.assertEqual(game.piece_at((9, 0)), ".")
        self.assertEqual(game.piece_at((0, 7)), ".")
        self.assertEqual(game.piece_at((9, 4)), "K")


if __name__ == "__main__":
    unittest.main()
