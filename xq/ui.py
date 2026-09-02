from __future__ import annotations

import time
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from .audio import Sounds
from .embedded_server import EmbeddedServer, local_ip
from .game import BLACK, RED, Game, Move, color_of, opponent
from .network import NetworkClient
from .storage import Storage


PIECE_TEXT = {
    "R": "车", "H": "马", "E": "相", "A": "仕", "K": "帅", "C": "炮", "P": "兵",
    "r": "车", "h": "马", "e": "象", "a": "士", "k": "将", "c": "炮", "p": "卒",
}


def chinese_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/system/fonts/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "Roboto"


FONT = chinese_font()


def emoji_font() -> str:
    for candidate in (
        Path("C:/Windows/Fonts/seguiemj.ttf"),
        Path("/system/fonts/NotoColorEmoji.ttf"),
    ):
        if candidate.exists():
            return str(candidate)
    return FONT


EMOJI_FONT = emoji_font()


def ui_label(text: str = "", **kwargs) -> Label:
    return Label(text=text, font_name=FONT, **kwargs)


def ui_button(text: str, callback, **kwargs) -> Button:
    button = Button(text=text, font_name=kwargs.pop("font_name", FONT), **kwargs)

    def released(instance):
        app = App.get_running_app()
        view = getattr(app, "view", None) if app else None
        if view and hasattr(view, "sounds"):
            view.sounds.play("click")
        callback(instance)

    button.bind(on_release=released)
    return button


class BoardWidget(Widget):
    def __init__(self, controller, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.game = Game()
        self.selected: tuple[int, int] | None = None
        self.last_move: Move | None = None
        self.flip = False
        self.bind(pos=lambda *_: self.redraw(), size=lambda *_: self.redraw())

    def set_game(self, game: Game, last_move: Move | None = None) -> None:
        self.game = game
        self.last_move = last_move
        if self.selected and color_of(game.piece_at(self.selected)) != game.turn:
            self.selected = None
        self.redraw()

    def geometry(self):
        margin = dp(24)
        usable_w = max(dp(10), self.width - 2 * margin)
        usable_h = max(dp(10), self.height - 2 * margin)
        step = min(usable_w / 8, usable_h / 9)
        width, height = step * 8, step * 9
        ox = self.x + (self.width - width) / 2
        oy = self.y + (self.height - height) / 2
        return ox, oy, step

    def board_to_screen(self, row: int, col: int):
        if self.flip:
            row, col = 9 - row, 8 - col
        ox, oy, step = self.geometry()
        return ox + col * step, oy + (9 - row) * step

    def screen_to_board(self, x: float, y: float):
        ox, oy, step = self.geometry()
        col = round((x - ox) / step)
        display_row = 9 - round((y - oy) / step)
        if not (0 <= col <= 8 and 0 <= display_row <= 9):
            return None
        px, py = ox + col * step, oy + (9 - display_row) * step
        if abs(x - px) > step * .48 or abs(y - py) > step * .48:
            return None
        return (9 - display_row, 8 - col) if self.flip else (display_row, col)

    def redraw(self) -> None:
        if self.width <= 1 or self.height <= 1:
            return
        ox, oy, step = self.geometry()
        with self.canvas:
            self.canvas.clear()
            Color(0.88, 0.70, 0.40, 1)
            Rectangle(pos=(ox - step * .45, oy - step * .45), size=(step * 8.9, step * 9.9))
            Color(0.18, 0.12, 0.07, 1)
            for row in range(10):
                y = oy + row * step
                Line(points=[ox, y, ox + 8 * step, y], width=1.1)
            for col in range(9):
                x = ox + col * step
                if col in (0, 8):
                    Line(points=[x, oy, x, oy + 9 * step], width=1.1)
                else:
                    Line(points=[x, oy, x, oy + 4 * step], width=1.1)
                    Line(points=[x, oy + 5 * step, x, oy + 9 * step], width=1.1)
            Line(points=[ox + 3 * step, oy, ox + 5 * step, oy + 2 * step], width=1.1)
            Line(points=[ox + 5 * step, oy, ox + 3 * step, oy + 2 * step], width=1.1)
            Line(points=[ox + 3 * step, oy + 7 * step, ox + 5 * step, oy + 9 * step], width=1.1)
            Line(points=[ox + 5 * step, oy + 7 * step, ox + 3 * step, oy + 9 * step], width=1.1)

            river = CoreLabel(text="楚 河        汉 界", font_name=FONT, font_size=step * .34, color=(.2, .12, .05, 1))
            river.refresh()
            Rectangle(texture=river.texture, pos=(ox + step * 1.7, oy + step * 4.2), size=river.texture.size)

            marked = set()
            if self.last_move:
                marked.update((self.last_move.src, self.last_move.dst))
            for row, col in marked:
                x, y = self.board_to_screen(row, col)
                Color(.1, .45, .85, .6)
                Line(circle=(x, y, step * .38), width=2)
            if self.selected:
                x, y = self.board_to_screen(*self.selected)
                Color(1, .85, .05, .9)
                Line(circle=(x, y, step * .43), width=3)

            for row in range(10):
                for col in range(9):
                    piece = self.game.board[row][col]
                    if piece == ".":
                        continue
                    x, y = self.board_to_screen(row, col)
                    radius = step * .39
                    Color(.96, .83, .56, 1)
                    Ellipse(pos=(x - radius, y - radius), size=(radius * 2, radius * 2))
                    Color(.35, .18, .07, 1)
                    Line(circle=(x, y, radius), width=1.4)
                    text_color = (.78, .05, .04, 1) if piece.isupper() else (.08, .08, .08, 1)
                    label = CoreLabel(text=PIECE_TEXT[piece], font_name=FONT, font_size=step * .46, color=text_color)
                    label.refresh()
                    Rectangle(texture=label.texture, pos=(x - label.texture.size[0] / 2, y - label.texture.size[1] / 2), size=label.texture.size)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        pos = self.screen_to_board(*touch.pos)
        if pos is None:
            return True
        piece = self.game.piece_at(pos)
        allowed = self.controller.can_select(pos)
        if self.selected:
            if allowed:
                self.selected = pos
            elif self.controller.try_move(Move(self.selected, pos)):
                self.selected = None
            self.redraw()
        elif piece != "." and allowed:
            self.selected = pos
            self.redraw()
        return True


class MenuScreen(Screen):
    def __init__(self, controller, **kwargs):
        super().__init__(name="menu", **kwargs)
        self.controller = controller
        root = BoxLayout(orientation="vertical", padding=dp(38), spacing=dp(18))
        root.add_widget(Widget(size_hint_y=.45))
        root.add_widget(ui_label("中国象棋", font_size=dp(38), size_hint_y=None, height=dp(64)))
        root.add_widget(ui_label("Python · 桌面与 Android", color=(.72, .72, .72, 1), size_hint_y=None, height=dp(32)))
        buttons = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None, height=dp(190))
        buttons.add_widget(ui_button("本地双人", lambda *_: controller.open_game_settings("local"), font_size=dp(20)))
        buttons.add_widget(ui_button("联机对弈", lambda *_: controller.open_online_menu(), font_size=dp(20)))
        buttons.add_widget(ui_button("历史棋局复盘", lambda *_: controller.open_history(), font_size=dp(20)))
        root.add_widget(buttons)
        root.add_widget(Widget(size_hint_y=.55))
        self.add_widget(root)
        root.size, root.pos = self.size, self.pos
        self.bind(size=lambda _widget, value: setattr(root, "size", value))
        self.bind(pos=lambda _widget, value: setattr(root, "pos", value))


class GameScreen(Screen):
    def __init__(self, controller, **kwargs):
        super().__init__(name="game", **kwargs)
        self.controller = controller
        root = BoxLayout(orientation="vertical", padding=dp(5), spacing=dp(3))
        bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        bar.add_widget(ui_button("主菜单", lambda *_: controller.leave_game(), size_hint_x=.22))
        self.status = ui_label("准备开始", font_size=dp(17))
        bar.add_widget(self.status)
        self.chat_button = ui_button("聊天", lambda *_: controller.open_chat(), size_hint_x=.16)
        bar.add_widget(self.chat_button)
        bar.add_widget(ui_button("悔棋", lambda *_: controller.request_undo(), size_hint_x=.18))
        root.add_widget(bar)
        self.connection_info = ui_label("", size_hint_y=None, height=0, color=(.85, .72, .25, 1))
        root.add_widget(self.connection_info)
        self.clock_label = ui_label("红方 --:--   黑方 --:--", size_hint_y=None, height=dp(30), font_size=dp(18))
        root.add_widget(self.clock_label)
        self.board = BoardWidget(controller)
        root.add_widget(self.board)
        self.add_widget(root)
        root.size, root.pos = self.size, self.pos
        self.bind(size=lambda _widget, value: setattr(root, "size", value))
        self.bind(pos=lambda _widget, value: setattr(root, "pos", value))

    def set_connection_info(self, text: str) -> None:
        self.connection_info.text = text
        self.connection_info.height = dp(28) if text else 0


class ReplayScreen(Screen):
    def __init__(self, controller, **kwargs):
        super().__init__(name="replay", **kwargs)
        self.controller = controller
        self.record = None
        self.step = 0
        self.root_box = BoxLayout(orientation="vertical", padding=dp(7), spacing=dp(5))
        self.header = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(5))
        self.header.add_widget(ui_button("返回", lambda *_: self.go_back(), size_hint_x=.22))
        self.title_label = ui_label("历史棋局", font_size=dp(21))
        self.header.add_widget(self.title_label)
        self.root_box.add_widget(self.header)
        self.content = BoxLayout(orientation="vertical")
        self.root_box.add_widget(self.content)
        self.add_widget(self.root_box)
        self.root_box.size, self.root_box.pos = self.size, self.pos
        self.bind(size=lambda _widget, value: setattr(self.root_box, "size", value))
        self.bind(pos=lambda _widget, value: setattr(self.root_box, "pos", value))

    def show_list(self) -> None:
        self.record = None
        self.title_label.text = "历史棋局"
        self.content.clear_widgets()
        records = self.controller.storage.history()
        if not records:
            self.content.add_widget(ui_label("还没有保存的棋局"))
            return
        scroll = ScrollView()
        listing = GridLayout(cols=1, spacing=dp(6), padding=dp(4), size_hint_y=None)
        listing.bind(minimum_height=listing.setter("height"))
        for record in records:
            winner = "红胜" if record.get("winner") == RED else "黑胜"
            mode = "本地" if record.get("mode") == "local" else "联机"
            text = f"{record.get('saved_at', '')}  {mode}  {winner} · {record.get('reason', '')}  {len(record.get('moves', []))}步"
            listing.add_widget(ui_button(text, lambda _btn, item=record: self.load_record(item), size_hint_y=None, height=dp(52)))
        scroll.add_widget(listing)
        self.content.add_widget(scroll)

    def load_record(self, record: dict) -> None:
        self.record, self.step = record, 0
        self.title_label.text = "棋局复盘"
        self.content.clear_widgets()
        self.status = ui_label("", size_hint_y=None, height=dp(34), font_size=dp(17))
        self.content.add_widget(self.status)
        self.board = BoardWidget(self)
        self.content.add_widget(self.board)
        nav = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(7))
        nav.add_widget(ui_button("上一步", lambda *_: self.change_step(-1)))
        nav.add_widget(ui_button("下一步", lambda *_: self.change_step(1)))
        nav.add_widget(ui_button("回到开局", lambda *_: self.set_step(0)))
        nav.add_widget(ui_button("跳到终局", lambda *_: self.set_step(len(record.get("moves", [])))))
        self.content.add_widget(nav)
        self.render_step()

    def change_step(self, amount: int) -> None:
        self.set_step(self.step + amount)

    def set_step(self, value: int) -> None:
        self.step = max(0, min(value, len(self.record.get("moves", []))))
        self.render_step()

    def render_step(self) -> None:
        settings = self.record.get("settings", {})
        handicap = [x.strip() for x in settings.get("handicap", "").split(",") if x.strip()]
        game = Game(handicap)
        last = None
        for move_data in self.record.get("moves", [])[:self.step]:
            last = Move.from_dict(move_data)
            game.make_move(last)
        suffix = ""
        if self.step == len(self.record.get("moves", [])):
            suffix = f" · 终局：{'红方' if self.record.get('winner') == RED else '黑方'}获胜（{self.record.get('reason', '')}）"
        self.status.text = f"第 {self.step}/{len(self.record.get('moves', []))} 步{suffix}"
        self.board.set_game(game, last)

    def go_back(self) -> None:
        if self.record:
            self.show_list()
        else:
            self.controller.current = "menu"

    def can_select(self, _pos) -> bool:
        return False

    def try_move(self, _move) -> bool:
        return False


class MainView(ScreenManager):
    def __init__(self, storage_path: str | Path, **kwargs):
        super().__init__(**kwargs)
        self.storage = Storage(storage_path)
        self.sounds = Sounds()
        self.network = NetworkClient(self._network_message, self._network_error)
        self.embedded_server = EmbeddedServer()
        self.mode = "local"
        self.my_color: str | None = None
        self.game = Game()
        self.game_settings = self.storage.settings
        self.move_history: list[dict] = []
        self.local_total = 0
        self.local_move = 0
        self.local_clocks = {RED: 0.0, BLACK: 0.0}
        self.local_clock_history: list[dict[str, float]] = []
        self.turn_started = time.monotonic()
        self.last_pending_undo: str | None = None
        self.finish_prompted = False
        self.chat_messages: list[dict] = []
        self.chat_popup = None
        self.chat_label = None
        self.chat_scroll = None
        self.add_widget(MenuScreen(self))
        self.game_screen = GameScreen(self)
        self.add_widget(self.game_screen)
        self.replay_screen = ReplayScreen(self)
        self.add_widget(self.replay_screen)
        Clock.schedule_interval(self.tick, .2)

    @property
    def board(self):
        return self.game_screen.board

    def open_game_settings(self, mode: str) -> None:
        saved = self.storage.settings
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(7))
        form = GridLayout(cols=2, spacing=dp(6))
        total = self._popup_field(form, "局时（分钟，0不限）", str(saved.get("total_minutes", 30)))
        per_move = self._popup_field(form, "步时（秒，0不限）", str(saved.get("move_seconds", 60)))
        handicap = self._popup_field(form, "让子（例 R1,H1）", saved.get("handicap", ""))
        room = port = None
        if mode == "host":
            room = self._popup_field(form, "房间号", saved.get("room", "xq001"))
            port = self._popup_field(form, "端口号", str(saved.get("port", 8765)))
        box.add_widget(form)
        popup = Popup(
            title="本局设置" if mode == "local" else "创建联机对局",
            title_font=FONT, content=box, size_hint=(.84, .68 if mode == "host" else .58), auto_dismiss=False,
        )

        def submit(*_):
            try:
                settings = self._parse_settings(total.text, per_move.text, handicap.text)
                if mode == "host":
                    settings["room"] = room.text.strip()
                    settings["port"] = int(port.text.strip())
                    if not settings["room"] or not 1 <= settings["port"] <= 65535:
                        raise ValueError("房间号不能为空，端口须为 1-65535")
            except ValueError as exc:
                self.show_error(str(exc))
                return
            self.storage.remember_settings({**saved, **settings})
            popup.dismiss()
            if mode == "local":
                self.start_local(settings)
            else:
                self.start_host(settings)

        buttons = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(7))
        buttons.add_widget(ui_button("取消", lambda *_: popup.dismiss()))
        buttons.add_widget(ui_button("开始", submit))
        box.add_widget(buttons)
        popup.open()

    def _popup_field(self, form, label: str, value: str) -> TextInput:
        form.add_widget(ui_label(label))
        field = TextInput(text=str(value), multiline=False, font_name=FONT)
        form.add_widget(field)
        return field

    @staticmethod
    def _parse_settings(total: str, per_move: str, handicap: str) -> dict:
        try:
            total_minutes = max(0, float(total.strip() or "0"))
            move_seconds = max(0, int(per_move.strip() or "0"))
        except ValueError as exc:
            raise ValueError("局时和步时必须是数字") from exc
        return {"total_minutes": total_minutes, "move_seconds": move_seconds, "handicap": handicap.strip()}

    def open_online_menu(self) -> None:
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(9))
        box.add_widget(ui_label("创建方会在本软件内启动服务，并显示供对方连接的 IP 和端口。"))
        popup = Popup(title="联机对弈", title_font=FONT, content=box, size_hint=(.78, .48), auto_dismiss=False)
        box.add_widget(ui_button("创建对局（本机作为主机）", lambda *_: (popup.dismiss(), self.open_game_settings("host"))))
        box.add_widget(ui_button("加入对局", lambda *_: (popup.dismiss(), self.open_join_settings())))
        box.add_widget(ui_button("取消", lambda *_: popup.dismiss()))
        popup.open()

    def open_join_settings(self) -> None:
        saved = self.storage.settings
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(7))
        form = GridLayout(cols=2, spacing=dp(6))
        host = self._popup_field(form, "主机 IP", saved.get("host", "127.0.0.1"))
        port = self._popup_field(form, "端口号", str(saved.get("port", 8765)))
        room = self._popup_field(form, "房间号", saved.get("room", "xq001"))
        box.add_widget(form)
        popup = Popup(title="加入联机对局", title_font=FONT, content=box, size_hint=(.82, .56), auto_dismiss=False)

        def submit(*_):
            try:
                port_number = int(port.text.strip())
                if not host.text.strip() or not room.text.strip() or not 1 <= port_number <= 65535:
                    raise ValueError
            except ValueError:
                self.show_error("请填写有效的主机 IP、端口和房间号")
                return
            updated = {**saved, "host": host.text.strip(), "port": port_number, "room": room.text.strip()}
            self.storage.remember_settings(updated)
            popup.dismiss()
            self.start_join(updated)

        buttons = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(7))
        buttons.add_widget(ui_button("取消", lambda *_: popup.dismiss()))
        buttons.add_widget(ui_button("连接", submit))
        box.add_widget(buttons)
        popup.open()

    def _prepare_game(self, mode: str, settings: dict) -> None:
        self.network.close()
        if mode != "host":
            self.embedded_server.stop()
        self.mode = "network" if mode in ("host", "join") else "local"
        self.my_color = None
        handicap = [x.strip() for x in settings.get("handicap", "").split(",") if x.strip()]
        self.game = Game(handicap)
        self.game_settings = settings.copy()
        self.move_history = []
        self.finish_prompted = False
        self.last_pending_undo = None
        self.chat_messages = []
        self.chat_popup = None
        self.chat_label = None
        self.chat_scroll = None
        self.game_screen.chat_button.text = "聊天"
        self.board.flip = False
        self.board.selected = None
        self.board.set_game(self.game)
        self.game_screen.set_connection_info("")
        self.current = "game"

    def start_local(self, settings: dict) -> None:
        self._prepare_game("local", settings)
        self.local_total = int(float(settings["total_minutes"]) * 60)
        self.local_move = int(settings["move_seconds"])
        self.local_clocks = {RED: float(self.local_total), BLACK: float(self.local_total)}
        self.local_clock_history = []
        self.turn_started = time.monotonic()
        self.game_screen.status.text = "本地双人 · 红方先行"

    def start_host(self, settings: dict) -> None:
        self._prepare_game("host", settings)
        port, room = int(settings["port"]), settings["room"]
        address = f"ws://{local_ip()}:{port}"
        self.game_screen.set_connection_info(f"对方连接：{address}   房间号：{room}")
        self.game_screen.status.text = "正在软件内启动联机服务…"

        def ready():
            Clock.schedule_once(lambda _dt: self._host_ready(port, room, settings), 0)

        self.embedded_server.start(port, ready, self._network_error)

    def _host_ready(self, port: int, room: str, settings: dict) -> None:
        self.game_screen.status.text = "等待对方加入"
        self.network.start(f"ws://127.0.0.1:{port}", {
            "action": "create", "room": room,
            "total_seconds": int(float(settings["total_minutes"]) * 60),
            "move_seconds": int(settings["move_seconds"]),
            "handicap": [x.strip() for x in settings.get("handicap", "").split(",") if x.strip()],
        })

    def start_join(self, settings: dict) -> None:
        self._prepare_game("join", settings)
        url = f"ws://{settings['host']}:{settings['port']}"
        self.game_screen.set_connection_info(f"连接：{url}   房间号：{settings['room']}")
        self.game_screen.status.text = "正在连接主机…"
        self.network.start(url, {"action": "join", "room": settings["room"]})

    def leave_game(self) -> None:
        def leave():
            self.network.close()
            self.embedded_server.stop()
            self.current = "menu"
        if self.move_history and not self.game.winner:
            self._confirm("离开对局", "当前棋局尚未结束，确定返回主菜单？", leave)
        else:
            leave()

    def open_history(self) -> None:
        self.replay_screen.show_list()
        self.current = "replay"

    def can_select(self, pos) -> bool:
        if self.current != "game" or self.game.winner:
            return False
        color = color_of(self.game.piece_at(pos))
        if self.mode == "network":
            return bool(self.my_color and color == self.my_color == self.game.turn)
        return color == self.game.turn

    def try_move(self, move: Move) -> bool:
        if not self.game.is_legal(move):
            self.game_screen.status.text = "非法走子"
            self.sounds.play("illegal")
            return False
        if self.mode == "network":
            if self.my_color != self.game.turn:
                return False
            self.network.send({"action": "move", "move": move.to_dict()})
            return True
        self.local_clock_history.append(self.local_clocks.copy())
        self._settle_local_clock()
        result = self.game.make_move(move)
        self.move_history.append(move.to_dict())
        self.turn_started = time.monotonic()
        self.sounds.play("capture" if result["captured"] else "move")
        if not self.game.winner and self.game.in_check(self.game.turn):
            Clock.schedule_once(lambda _dt: self.sounds.play("check"), .16)
        self.board.set_game(self.game, move)
        self._update_status()
        self._maybe_offer_save()
        return True

    def request_undo(self) -> None:
        if self.mode == "local":
            if not self.game.history:
                self.show_error("没有可以悔棋的步骤")
            else:
                self._confirm("悔棋请求", "对方请求悔棋，是否同意？", self._local_undo)
        else:
            self.network.send({"action": "undo_request"})
            self.game_screen.status.text = "已请求悔棋，等待对方同意"

    def open_chat(self) -> None:
        if self.mode != "network":
            self.show_error("聊天和表情功能仅在联机对局中使用")
            return
        box = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(6))
        scroll = ScrollView()
        self.chat_scroll = scroll
        self.chat_label = ui_label("", size_hint_y=None, halign="left", valign="top")
        self.chat_label.bind(width=lambda label, width: setattr(label, "text_size", (width - dp(12), None)))
        self.chat_label.bind(texture_size=lambda label, size: setattr(label, "height", max(size[1] + dp(12), dp(40))))
        scroll.add_widget(self.chat_label)
        box.add_widget(scroll)
        emojis = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        for emoji in ("😀", "😂", "👍", "👏", "🤔", "😮"):
            emojis.add_widget(ui_button(
                emoji, lambda _btn, value=emoji: self.send_chat(value, "emoji"),
                font_size=dp(22), font_name=EMOJI_FONT,
            ))
        box.add_widget(emojis)
        send_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        self.chat_input = TextInput(hint_text="输入消息（最多200字）", multiline=False, font_name=FONT)
        self.chat_input.bind(on_text_validate=lambda *_: self.send_chat(self.chat_input.text, "text"))
        send_row.add_widget(self.chat_input)
        send_row.add_widget(ui_button("发送", lambda *_: self.send_chat(self.chat_input.text, "text"), size_hint_x=.22))
        box.add_widget(send_row)
        popup = Popup(title="对局聊天", title_font=FONT, content=box, size_hint=(.86, .72))
        self.chat_popup = popup
        popup.bind(on_dismiss=lambda *_: self._close_chat())
        self.game_screen.chat_button.text = "聊天"
        self._refresh_chat()
        popup.open()

    def _close_chat(self) -> None:
        self.chat_popup = None
        self.chat_label = None
        self.chat_scroll = None

    def send_chat(self, text: str, kind: str = "text") -> None:
        text = str(text).strip()
        if not text:
            return
        if len(text) > 200:
            self.show_error("消息不能超过 200 个字符")
            return
        self.network.send({"action": "chat", "text": text, "kind": kind})
        if hasattr(self, "chat_input") and kind == "text":
            self.chat_input.text = ""

    def _refresh_chat(self) -> None:
        if not self.chat_label:
            return
        lines = []
        emoji_names = {"😀": "开心", "😂": "大笑", "👍": "赞", "👏": "鼓掌", "🤔": "思考", "😮": "惊讶"}
        for message in self.chat_messages:
            side = "红方" if message.get("color") == RED else "黑方"
            text = message.get("text", "")
            if message.get("kind") == "emoji":
                text = f"[表情·{emoji_names.get(text, text)}]"
            lines.append(f"{side}：{text}")
        self.chat_label.text = "\n\n".join(lines) if lines else "暂无消息"
        if self.chat_scroll:
            Clock.schedule_once(lambda _dt: setattr(self.chat_scroll, "scroll_y", 0) if self.chat_scroll else None, 0)

    def _local_undo(self) -> None:
        if self.game.undo():
            if self.local_clock_history:
                self.local_clocks = self.local_clock_history.pop()
            if self.move_history:
                self.move_history.pop()
            self.turn_started = time.monotonic()
            self.board.set_game(self.game)
            self._update_status("对方已同意悔棋")

    def _network_message(self, message: dict) -> None:
        Clock.schedule_once(lambda _dt: self.handle_network_message(message), 0)

    def _network_error(self, message: str) -> None:
        if message:
            Clock.schedule_once(lambda _dt: self.show_error(f"网络错误：{message}"), 0)

    def handle_network_message(self, message: dict) -> None:
        kind = message.get("type")
        if kind == "error":
            self.show_error(message.get("message", "服务器返回错误"))
            return
        if kind == "joined":
            self.my_color = message["color"]
            self.board.flip = self.my_color == BLACK
            self.game_screen.status.text = f"已加入房间，你执{'红' if self.my_color == RED else '黑'}"
            return
        if kind == "chat":
            entry = message.get("message", {})
            if entry and not any(item.get("id") == entry.get("id") for item in self.chat_messages):
                self.chat_messages.append(entry)
                self.chat_messages = self.chat_messages[-100:]
                if not self.chat_popup and entry.get("color") != self.my_color:
                    self.game_screen.chat_button.text = "聊天 •"
                self._refresh_chat()
            return
        if kind != "state":
            return
        old_moves = len(self.move_history)
        self.game = Game.from_state(message["game"])
        self.move_history = list(message.get("moves", self.move_history))
        self.chat_messages = list(message.get("chat", self.chat_messages))
        self._refresh_chat()
        self.game.history = [{}] * len(self.move_history)
        last_move = Move.from_dict(self.move_history[-1]) if self.move_history else None
        self.board.set_game(self.game, last_move)
        if len(self.move_history) > old_moves:
            self.sounds.play("capture" if message.get("captured") else "move")
            if not self.game.winner and self.game.in_check(self.game.turn):
                Clock.schedule_once(lambda _dt: self.sounds.play("check"), .16)
        settings = message.get("settings", {})
        if settings:
            remembered_gameplay = {
                "total_minutes": settings.get("total_seconds", 0) / 60,
                "move_seconds": settings.get("move_seconds", 0),
                "handicap": ",".join(settings.get("handicap", [])),
            }
            self.game_settings.update(remembered_gameplay)
            saved = self.storage.settings
            if any(saved.get(key) != value for key, value in remembered_gameplay.items()):
                self.storage.remember_settings({**saved, **remembered_gameplay})
        self.game_screen.clock_label.text = self._clock_text(message.get("clocks", {}), message.get("move_remaining", 0))
        pending = message.get("pending_undo")
        if pending and pending != self.my_color and pending != self.last_pending_undo:
            self._confirm(
                "联网悔棋请求", "对方请求悔棋，是否同意？",
                lambda: self.network.send({"action": "undo_answer", "accept": True}),
                lambda: self.network.send({"action": "undo_answer", "accept": False}),
            )
        self.last_pending_undo = pending
        if message.get("notice"):
            self.game_screen.status.text = message["notice"]
        elif message.get("undo_result"):
            self.game_screen.status.text = "悔棋已执行" if message["undo_result"] == "accepted" else "悔棋请求被拒绝"
        else:
            self._update_status("对局中" if message.get("started") else "等待对手加入")
        self._maybe_offer_save()

    def _settle_local_clock(self) -> None:
        if self.local_total > 0:
            elapsed = time.monotonic() - self.turn_started
            self.local_clocks[self.game.turn] = max(0.0, self.local_clocks[self.game.turn] - elapsed)

    def tick(self, _dt) -> None:
        if self.mode != "local" or self.current != "game":
            return
        clocks = self.local_clocks.copy()
        elapsed = time.monotonic() - self.turn_started
        if not self.game.winner:
            if self.local_total > 0:
                clocks[self.game.turn] = max(0.0, clocks[self.game.turn] - elapsed)
            total_expired = self.local_total > 0 and clocks[self.game.turn] <= 0
            move_expired = self.local_move > 0 and elapsed >= self.local_move
            if total_expired or move_expired:
                self.game.winner = opponent(self.game.turn)
                self.game.reason = "局时超时" if total_expired else "步时超时"
                self.local_clocks = clocks
                self.board.redraw()
                self._update_status()
                self._maybe_offer_save()
        move_remaining = max(0, self.local_move - elapsed) if self.local_move > 0 else 0
        self.game_screen.clock_label.text = self._clock_text(clocks, move_remaining)

    def _clock_text(self, clocks, move_remaining=0) -> str:
        def fmt(value):
            if not clocks or self.mode == "local" and self.local_total == 0:
                return "不限"
            value = max(0, int(value or 0))
            return f"{value // 60:02d}:{value % 60:02d}"
        move_text = f"  本步 {int(move_remaining)}秒" if move_remaining else ""
        return f"红方 {fmt(clocks.get(RED, 0))}   黑方 {fmt(clocks.get(BLACK, 0))}{move_text}"

    def _update_status(self, prefix: str = "") -> None:
        if self.game.winner:
            self.game_screen.status.text = f"{'红方' if self.game.winner == RED else '黑方'}获胜：{self.game.reason}"
        else:
            turn = "红方" if self.game.turn == RED else "黑方"
            check = "，将军！" if self.game.in_check(self.game.turn) else ""
            self.game_screen.status.text = f"{prefix + ' · ' if prefix else ''}{turn}走{check}"

    def _maybe_offer_save(self) -> None:
        if not self.game.winner or self.finish_prompted:
            return
        self.finish_prompted = True
        Clock.schedule_once(lambda _dt: self._confirm(
            "保存棋局", "本局已经结束，是否保存到历史棋局？", self.save_current_game
        ), .15)

    def save_current_game(self) -> None:
        self.storage.save_game({
            "mode": self.mode, "settings": self.game_settings,
            "moves": self.move_history, "winner": self.game.winner, "reason": self.game.reason,
        })
        self.game_screen.status.text += " · 已保存"

    def show_error(self, text: str) -> None:
        if self.current == "game":
            self.game_screen.status.text = text
        Popup(title="提示", title_font=FONT, content=ui_label(text), size_hint=(.75, .3)).open()

    def _confirm(self, title: str, text: str, yes, no=lambda: None) -> None:
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        box.add_widget(ui_label(text))
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(44))
        popup = Popup(title=title, title_font=FONT, content=box, size_hint=(.8, .38), auto_dismiss=False)
        row.add_widget(ui_button("同意", lambda *_: (popup.dismiss(), yes())))
        row.add_widget(ui_button("拒绝", lambda *_: (popup.dismiss(), no())))
        box.add_widget(row)
        popup.open()

    def shutdown(self) -> None:
        self.network.close()
        self.embedded_server.stop()


class ChineseChessApp(App):
    title = "Python 中国象棋"

    def build(self):
        self.view = MainView(Path(self.user_data_dir) / "xq_data.json")
        return self.view

    def on_stop(self):
        self.view.shutdown()
