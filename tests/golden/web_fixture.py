"""Loopback-only HTTP server for the deterministic UI graph fixture."""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


DEFAULT_WEB_ROOT = Path(__file__).resolve().parent / 'v1' / 'web'


class _FixtureHandler(SimpleHTTPRequestHandler):
    server_version = 'TestHubGoldenFixture/1.0'

    def log_message(self, format, *args):  # noqa: A002 - stdlib API name
        return

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-TestHub-Fixture', 'wp-001-v1')
        super().end_headers()


class GoldenWebServer:
    """Serve the checked-in fixture on 127.0.0.1 using an ephemeral port."""

    def __init__(self, root: Path | str = DEFAULT_WEB_ROOT):
        self.root = Path(root).resolve()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError('GoldenWebServer has not been started')
        host, port = self._server.server_address[:2]
        return f'http://{host}:{port}'

    def url(self, relative_path: str) -> str:
        normalized = relative_path.lstrip('/')
        return f'{self.base_url}/{quote(normalized, safe="/?=&")}'

    def start(self) -> 'GoldenWebServer':
        if self._server is not None:
            return self
        if not self.root.is_dir():
            raise FileNotFoundError(self.root)
        handler = functools.partial(_FixtureHandler, directory=str(self.root))
        self._server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name='golden-web-fixture', daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> 'GoldenWebServer':
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()
