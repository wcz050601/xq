"""Open the real Kivy UI briefly and save a screenshot for layout verification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kivy.config import Config

Config.set("graphics", "width", "540")
Config.set("graphics", "height", "900")
Config.set("graphics", "resizable", "0")

from kivy.clock import Clock
from kivy.core.window import Window

from xq.game import Move
from xq.ui import ChineseChessApp, MainView


class SmokeApp(ChineseChessApp):
    def build(self):
        self.view = MainView(Path.cwd() / ".kivy-home" / "smoke_data.json")
        return self.view

    def on_start(self):
        Clock.schedule_once(lambda _dt: self.root.get_screen("menu").export_to_png("ui-menu-smoke.png"), .6)
        Clock.schedule_once(self.start_test_game, 1.0)
        Clock.schedule_once(lambda _dt: self.root.get_screen("game").export_to_png("ui-game-smoke.png"), 1.7)
        Clock.schedule_once(self.open_test_chat, 2.1)
        Clock.schedule_once(lambda _dt: self.root.chat_popup.content.export_to_png("ui-chat-smoke.png"), 2.7)
        Clock.schedule_once(lambda _dt: self.stop(), 3.3)

    def start_test_game(self, _dt):
        self.root.start_local({"total_minutes": 30, "move_seconds": 60, "handicap": ""})
        assert self.root.try_move(Move((6, 0), (5, 0)))

    def open_test_chat(self, _dt):
        self.root.mode = "network"
        self.root.chat_messages = [
            {"id": 1, "color": "red", "text": "你好，开始吧", "kind": "text"},
            {"id": 2, "color": "black", "text": "👍", "kind": "emoji"},
        ]
        self.root.open_chat()


if __name__ == "__main__":
    SmokeApp().run()
