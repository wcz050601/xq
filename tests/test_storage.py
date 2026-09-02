import tempfile
import unittest
from pathlib import Path

from xq.storage import Storage


class StorageTests(unittest.TestCase):
    def test_settings_survive_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            store = Storage(path)
            store.remember_settings({"total_minutes": 12, "move_seconds": 8, "handicap": "R1"})
            loaded = Storage(path)
            self.assertEqual(loaded.settings["total_minutes"], 12)
            self.assertEqual(loaded.settings["handicap"], "R1")

    def test_saved_game_is_listed_newest_first(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "data.json")
            first = store.save_game({"moves": [], "winner": "red", "reason": "将死"})
            second = store.save_game({"moves": [{"src": [6, 0], "dst": [5, 0]}], "winner": "black", "reason": "超时"})
            self.assertEqual(store.history()[0]["id"], second["id"])
            self.assertEqual(store.history()[1]["id"], first["id"])


if __name__ == "__main__":
    unittest.main()

