"""Uvicorn entrypoint for Story Pointer.

Usage:
    python run.py                 # dev server on 127.0.0.1:8000
    python run.py --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

import uvicorn

from story_pointer.config import get_settings


def _url_available(url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - operator-configured URL
            return response.status < 500
    except (OSError, URLError):
        return False


def _phoenix_executable() -> str:
    """Find the Phoenix CLI installed beside the active Python interpreter."""
    name = "phoenix.exe" if os.name == "nt" else "phoenix"
    adjacent = Path(sys.executable).with_name(name)
    if adjacent.exists():
        return str(adjacent)
    found = shutil.which("phoenix")
    if found:
        return found
    raise RuntimeError(
        "Phoenix CLI not found. Install project dependencies with "
        "'python -m pip install -r requirements.txt'."
    )


def _start_phoenix(settings) -> subprocess.Popen | None:
    """Start a local Phoenix collector unless the configured UI is already up."""
    if _url_available(settings.phoenix_ui_url):
        print(f"Phoenix already running at {settings.phoenix_ui_url}")
        return None

    parsed = urlsplit(settings.phoenix_ui_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError(f"Invalid PHOENIX_UI_URL: {settings.phoenix_ui_url}")

    env = os.environ.copy()
    env["PHOENIX_HOST"] = parsed.hostname
    env["PHOENIX_PORT"] = str(parsed.port or (443 if parsed.scheme == "https" else 80))
    env["PHOENIX_WORKING_DIR"] = str(Path(settings.phoenix_working_dir).resolve())

    command = [_phoenix_executable(), "serve"]
    print(f"Starting Phoenix at {settings.phoenix_ui_url} ...")
    process = subprocess.Popen(command, env=env)  # noqa: S603 - fixed installed CLI
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Phoenix exited during startup with code {process.returncode}")
        if _url_available(settings.phoenix_ui_url, timeout=2.0):
            print(f"Phoenix monitoring ready: {settings.phoenix_ui_url}")
            return process
        time.sleep(0.5)

    process.terminate()
    raise RuntimeError(f"Timed out waiting for Phoenix at {settings.phoenix_ui_url}")


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Story Pointer API server.")
    parser.add_argument("--host", default=None, help="Bind host (default: from settings).")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: from settings).")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only).")
    parser.add_argument(
        "--with-phoenix",
        action="store_true",
        help="Start the local Phoenix collector/UI before the API and stop it on exit.",
    )
    args = parser.parse_args()

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port

    phoenix_process = None
    try:
        if args.with_phoenix:
            if not settings.phoenix_enabled:
                raise RuntimeError("--with-phoenix requires PHOENIX_ENABLED=true")
            phoenix_process = _start_phoenix(settings)

        uvicorn.run(
            "story_pointer.api:app",
            host=host,
            port=port,
            reload=args.reload,
        )
    finally:
        _stop_process(phoenix_process)


if __name__ == "__main__":
    main()
