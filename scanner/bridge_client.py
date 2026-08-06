"""
Python client for FingerprintBridge.exe (openfinger capture bridge).

The bridge exe wraps the DigitalPersona DPFP SDK and emits one JSON line per
event on stdout — status, scan, error. This module spawns the exe (or attaches
to its named pipe if it's already running) and lets you consume events in
either a callback or a blocking iterator style.

Two usage patterns:

    # 1. Callback style
    from openfinger.scanner import ScannerBridge

    def on_event(evt):
        if evt["type"] == "scan":
            with open("finger.png", "wb") as f:
                f.write(evt["data"])

    bridge = ScannerBridge(on_event=on_event)
    bridge.start()
    input("Press Enter to stop...")
    bridge.stop()

    # 2. Blocking iterator
    with ScannerBridge() as bridge:
        for evt in bridge.events():
            if evt["type"] == "scan":
                ...  # process bytes

Events dict shape:
    {"type": "status",  "status": "ready" | "scanning" | "disconnected"}
    {"type": "scan",    "width": int, "height": int, "data": bytes}   # PNG bytes
    {"type": "error",   "code": str, "message": str}
"""
from __future__ import annotations

import json
import logging
import queue
import subprocess
import sys
import threading
import time
from base64 import b64decode
from pathlib import Path
from typing import Callable, Iterator, Optional

logger = logging.getLogger("openfinger.scanner")

PIPE_NAME = r"\\.\pipe\OpenFingerCapture"

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
_BRIDGE_EXE_CANDIDATES = [
    _REPO_ROOT / "bridge" / "FingerprintBridge.exe",
    _HERE.parent / "bridge" / "FingerprintBridge.exe",
]


def _find_bridge_exe() -> Optional[Path]:
    for p in _BRIDGE_EXE_CANDIDATES:
        if p.exists():
            return p
    return None


EventCallback = Callable[[dict], None]


class ScannerBridge:
    """Connects to the fingerprint bridge and streams events.

    Args:
        on_event: optional callback invoked from the reader thread whenever a
                  new event arrives. If omitted, use `events()` to iterate.
        exe_path: override the auto-detected FingerprintBridge.exe location.
    """

    def __init__(
        self,
        on_event: Optional[EventCallback] = None,
        exe_path: Optional[Path] = None,
    ) -> None:
        self._on_event = on_event
        self._exe_path = Path(exe_path) if exe_path else None
        self._queue: "queue.Queue[dict]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._status = "disconnected"

    # ── Context manager ────────────────────────────────────────────────
    def __enter__(self) -> "ScannerBridge":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ── Public API ─────────────────────────────────────────────────────
    @property
    def status(self) -> str:
        return self._status

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if sys.platform != "win32":
            raise RuntimeError(
                "FingerprintBridge.exe is Windows-only. "
                "On Linux/macOS run the exe under Wine, or replace this "
                "capture layer with your platform's fingerprint SDK."
            )
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ScannerBridge"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3.0)

    def events(self, timeout: Optional[float] = None) -> Iterator[dict]:
        """Yield events until stop() is called or timeout on a single wait."""
        while not self._stop.is_set():
            try:
                yield self._queue.get(timeout=timeout if timeout else 1.0)
            except queue.Empty:
                if timeout is not None:
                    return

    def wait_for_scan(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Block until a single scan arrives; return its PNG bytes."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self._stop.is_set():
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if deadline is not None and remaining == 0.0:
                return None
            try:
                evt = self._queue.get(timeout=remaining if remaining else 1.0)
            except queue.Empty:
                if deadline is not None:
                    return None
                continue
            if evt.get("type") == "scan":
                return evt.get("data")
        return None

    # ── Internal ───────────────────────────────────────────────────────
    def _emit(self, event: dict) -> None:
        self._queue.put(event)
        if self._on_event:
            try:
                self._on_event(event)
            except Exception:
                logger.exception("on_event callback raised")

    def _set_status(self, s: str) -> None:
        if self._status != s:
            self._status = s
            self._emit({"type": "status", "status": s})

    def _run(self) -> None:
        delay = 2.0
        while not self._stop.is_set():
            if self._try_pipe():
                delay = 2.0
                continue
            if self._spawn_exe_blocking():
                delay = 2.0
                continue
            self._set_status("disconnected")
            self._stop.wait(min(delay, 30.0))
            delay = min(delay * 2, 30.0)

    def _try_pipe(self) -> bool:
        try:
            f = open(PIPE_NAME, "rb", buffering=0)
        except (FileNotFoundError, OSError):
            return False
        logger.info("Connected to fingerprint bridge via named pipe")
        self._set_status("ready")
        self._read_lines(f)
        return True

    def _spawn_exe_blocking(self) -> bool:
        exe = self._exe_path or _find_bridge_exe()
        if not exe or not exe.exists():
            logger.warning(
                "FingerprintBridge.exe not found (searched %s). "
                "Rebuild via bridge/build.bat or set exe_path=...",
                ", ".join(str(p) for p in _BRIDGE_EXE_CANDIDATES),
            )
            return False
        logger.info("Starting fingerprint bridge exe: %s", exe)
        try:
            self._proc = subprocess.Popen(
                [str(exe)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except Exception as exc:
            logger.error("Failed to spawn bridge exe: %s", exc)
            return False
        start = time.monotonic()
        self._set_status("ready")
        try:
            self._read_lines(self._proc.stdout)
        finally:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
        return (time.monotonic() - start) > 3.0

    def _read_lines(self, stream) -> None:
        try:
            for raw in iter(stream.readline, b""):
                if self._stop.is_set():
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Bridge non-JSON: %s", line)
                    continue
                self._handle_msg(msg)
        except Exception as exc:
            logger.warning("Bridge stream error: %s", exc)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _handle_msg(self, msg: dict) -> None:
        t = msg.get("type")
        if t == "status":
            self._set_status(
                "ready" if msg.get("status") == "ready" else "disconnected"
            )
        elif t == "scan":
            self._set_status("scanning")
            try:
                data = b64decode(msg.get("data", ""))
            except Exception:
                data = b""
            self._emit({
                "type": "scan",
                "width": int(msg.get("width", 0)),
                "height": int(msg.get("height", 0)),
                "data": data,
            })
            self._set_status("ready")
        elif t == "error":
            logger.error("Bridge error [%s]: %s", msg.get("code"), msg.get("message"))
            self._emit({
                "type": "error",
                "code": msg.get("code"),
                "message": msg.get("message"),
            })


if __name__ == "__main__":
    # Smoke test: capture 3 fingerprints and save them as png files.
    import time as _t

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("Place your finger on the reader. Capturing 3 scans...")

    n = 0
    with ScannerBridge() as bridge:
        for evt in bridge.events():
            if evt["type"] == "scan":
                out = Path(f"capture_{n}.png")
                out.write_bytes(evt["data"])
                print(f"  saved {out} ({len(evt['data'])} bytes)")
                n += 1
                if n >= 3:
                    break
            elif evt["type"] == "error":
                print(f"  bridge error [{evt['code']}]: {evt['message']}")
    print("Done.")
