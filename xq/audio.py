from __future__ import annotations

import logging
from pathlib import Path


EVENT_FILES = {
    "move": "move.wav",
    "capture": "capture.wav",
    "check": "check.wav",
    "illegal": "illegal.wav",
    "click": "click.wav",
}


class Sounds:
    """Load event sounds, preferring SDL2 when GStreamer lacks WAV codecs."""

    def __init__(self):
        self.items: dict[str, object] = {}
        self.errors: list[str] = []
        root = Path(__file__).resolve().parent.parent / "assets" / "sounds"
        for event, filename in EVENT_FILES.items():
            path = root / filename
            if not path.exists():
                self.errors.append(f"缺少音效文件：{filename}")
                continue
            sound = self._load(path)
            if sound:
                sound.volume = 1.0
                self.items[event] = sound
            else:
                self.errors.append(f"无法加载音效：{filename}")
        for error in self.errors:
            logging.warning(error)

    @staticmethod
    def _load(path: Path):
        # Kivy may register GStreamer first even when its WAV decoder is absent.
        # SDL2 is bundled with Kivy and handles our PCM WAV files directly.
        try:
            from kivy.core.audio.audio_sdl2 import SoundSDL2
            sound = SoundSDL2(source=str(path))
            if sound.length > 0:
                return sound
        except Exception:
            pass
        try:
            from kivy.core.audio import SoundLoader
            return SoundLoader.load(str(path))
        except Exception:
            return None

    def play(self, event: str) -> None:
        sound = self.items.get(event)
        if not sound:
            return
        try:
            if sound.state == "play":
                sound.stop()
            sound.play()
        except Exception as exc:
            logging.warning("播放音效 %s 失败：%s", event, exc)
