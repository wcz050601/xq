from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


DEFAULT_SETTINGS = {"total_minutes": 30, "move_seconds": 60, "handicap": ""}


class Storage:
    """Small JSON store for remembered settings and saved game records."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = {"settings": DEFAULT_SETTINGS.copy(), "history": []}
        self.load()

    def load(self) -> None:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                self.data["settings"].update(saved.get("settings", {}))
                if isinstance(saved.get("history"), list):
                    self.data["history"] = saved["history"]
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            pass

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @property
    def settings(self) -> dict:
        return self.data["settings"].copy()

    def remember_settings(self, settings: dict) -> None:
        self.data["settings"] = {**DEFAULT_SETTINGS, **settings}
        self.flush()

    def save_game(self, record: dict) -> dict:
        saved = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            **record,
        }
        self.data["history"].insert(0, saved)
        self.flush()
        return saved

    def history(self) -> list[dict]:
        return list(self.data["history"])

