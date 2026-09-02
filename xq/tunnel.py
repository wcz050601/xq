from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path


RELEASE_API = "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"
TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


def parse_tunnel_url(text: str) -> str | None:
    match = TUNNEL_URL_RE.search(text)
    return match.group(0).replace("https://", "wss://", 1) if match else None


def normalize_server_url(value: str, port: int) -> str:
    value = value.strip().rstrip("/")
    if value.startswith("https://"):
        return "wss://" + value[8:]
    if value.startswith("http://"):
        return "ws://" + value[7:]
    if value.startswith(("ws://", "wss://")):
        return value
    return f"ws://{value}:{port}"


class QuickTunnel:
    """Manage a zero-configuration Cloudflare Quick Tunnel on Windows."""

    def __init__(self, tools_dir: str | Path):
        self.tools_dir = Path(tools_dir)
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.stop_flag = threading.Event()

    def start(
        self,
        port: int,
        on_status: Callable[[str], None],
        on_ready: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.stop()
        self.stop_flag = threading.Event()
        self.thread = threading.Thread(
            target=self._run, args=(port, on_status, on_ready, on_error), daemon=True
        )
        self.thread.start()

    def _run(self, port: int, on_status, on_ready, on_error) -> None:
        try:
            executable = self._ensure_binary(on_status)
            if self.stop_flag.is_set():
                return
            on_status("正在建立免费公网隧道…")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.process = subprocess.Popen(
                [
                    str(executable), "tunnel", "--no-autoupdate",
                    "--protocol", "http2", "--url", f"http://127.0.0.1:{port}",
                ],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", creationflags=flags,
            )
            recent = []
            assert self.process.stdout is not None
            for line in self.process.stdout:
                recent.append(line.strip())
                recent = recent[-8:]
                url = parse_tunnel_url(line)
                if url:
                    on_ready(url)
                    # Keep draining output so cloudflared cannot block on a full pipe.
                    for _line in self.process.stdout:
                        if self.stop_flag.is_set():
                            break
                    return
                if self.stop_flag.is_set():
                    return
            if not self.stop_flag.is_set():
                detail = next((item for item in reversed(recent) if item), "cloudflared 已退出")
                raise RuntimeError(detail)
        except Exception as exc:
            if not self.stop_flag.is_set():
                on_error(str(exc))
        finally:
            self._terminate_process()

    def _ensure_binary(self, on_status) -> Path:
        if platform.system() != "Windows" or platform.machine().lower() not in ("amd64", "x86_64"):
            raise RuntimeError("一键公网房间目前仅支持 64 位 Windows 创建；安卓和其他平台可以加入")
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        executable = self.tools_dir / "cloudflared.exe"
        if executable.exists() and executable.stat().st_size > 1_000_000:
            return executable

        on_status("首次使用：正在从 Cloudflare 官方仓库下载穿透组件…")
        request = urllib.request.Request(RELEASE_API, headers={"User-Agent": "pyxq/0.1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            release = json.load(response)
        asset = next(
            (item for item in release.get("assets", []) if item.get("name") == "cloudflared-windows-amd64.exe"),
            None,
        )
        if not asset:
            raise RuntimeError("Cloudflare 发布页中没有找到 Windows 64 位组件")
        temporary = executable.with_suffix(".download")
        digest = hashlib.sha256()
        download = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "pyxq/0.1"})
        total = int(asset.get("size") or 0)
        received = 0
        try:
            with urllib.request.urlopen(download, timeout=60) as response, temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if total:
                        on_status(f"首次下载穿透组件：{received * 100 // total}%")
            expected = str(asset.get("digest") or "")
            if expected.startswith("sha256:") and digest.hexdigest().lower() != expected[7:].lower():
                raise RuntimeError("穿透组件校验失败，已拒绝运行")
            temporary.replace(executable)
        finally:
            if temporary.exists():
                temporary.unlink()
        return executable

    def _terminate_process(self) -> None:
        process, self.process = self.process, None
        if not process or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

    def stop(self) -> None:
        self.stop_flag.set()
        self._terminate_process()
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)
        self.thread = None
