from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path


RELEASE_API = "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"
DIRECT_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
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
            public_url = None
            registered = False
            ready = False
            assert self.process.stdout is not None
            for line in self.process.stdout:
                recent.append(line.strip())
                recent = recent[-8:]
                url = parse_tunnel_url(line)
                if url:
                    public_url = url
                    on_status("公网地址已生成，正在等待证书和路由生效…")
                if "registered tunnel connection" in line.lower():
                    registered = True
                if public_url and registered and not ready:
                    self._wait_until_public_ready(public_url, on_status)
                    if self.stop_flag.is_set():
                        return
                    on_ready(public_url)
                    ready = True
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
        download_url, total, expected = self._download_source(on_status)
        temporary = executable.with_suffix(".download")
        digest = hashlib.sha256()
        download = urllib.request.Request(download_url, headers={"User-Agent": "pyxq/0.1"})
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
                    elif received:
                        on_status(f"首次下载穿透组件：{received // 1024 // 1024} MB")
            if received <= 1_000_000:
                raise RuntimeError("下载的穿透组件不完整，请检查网络后重试")
            if expected.startswith("sha256:") and digest.hexdigest().lower() != expected[7:].lower():
                raise RuntimeError("穿透组件校验失败，已拒绝运行")
            temporary.replace(executable)
        finally:
            if temporary.exists():
                temporary.unlink()
        return executable

    @staticmethod
    def _download_source(on_status) -> tuple[str, int, str]:
        """Prefer release metadata for its digest, but never depend on API quota."""
        try:
            request = urllib.request.Request(RELEASE_API, headers={"User-Agent": "pyxq/0.1"})
            with urllib.request.urlopen(request, timeout=20) as response:
                release = json.load(response)
            asset = next(
                item for item in release.get("assets", [])
                if item.get("name") == "cloudflared-windows-amd64.exe"
            )
            return (
                asset["browser_download_url"],
                int(asset.get("size") or 0),
                str(asset.get("digest") or ""),
            )
        except (OSError, ValueError, KeyError, StopIteration):
            on_status("GitHub 接口受限，正在改用官方最新版直链…")
            return DIRECT_DOWNLOAD_URL, 0, ""

    def _wait_until_public_ready(self, url: str, on_status, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        attempt = 0
        last_error = "公网端点尚未响应"
        while time.monotonic() < deadline and not self.stop_flag.is_set():
            attempt += 1
            ready, last_error = self._probe_public_url(url)
            if ready:
                return
            on_status(f"公网证书和路由准备中（第 {attempt} 次检测）…")
            self.stop_flag.wait(2)
        if not self.stop_flag.is_set():
            raise RuntimeError(f"公网地址在 60 秒内未就绪：{last_error}")

    @staticmethod
    def _probe_public_url(url: str) -> tuple[bool, str]:
        """Confirm TLS hostname validity and that Cloudflare can route to the origin."""
        import certifi

        https_url = "https://" + url.removeprefix("wss://")
        request = urllib.request.Request(
            https_url,
            headers={"User-Agent": "pyxq/0.1", "Connection": "close"},
        )
        context = ssl.create_default_context(cafile=certifi.where())
        try:
            with urllib.request.urlopen(request, timeout=6, context=context):
                return True, ""
        except urllib.error.HTTPError as exc:
            # A WebSocket-only origin normally returns 400/426 to this plain HTTPS
            # request. That still proves TLS and tunnel routing are both ready.
            if exc.code < 500:
                return True, ""
            return False, f"Cloudflare HTTP {exc.code}"
        except (OSError, urllib.error.URLError) as exc:
            return False, str(exc)

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
