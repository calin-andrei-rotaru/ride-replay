"""Serve a private comparison through the existing dashboard on loopback only."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .snapshot import validate_public_snapshot


def preview_server(snapshot_path: Path, web_root: Path, port: int = 8765):
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validate_public_snapshot(snapshot)
    root = web_root.resolve()
    if not (root / "index.html").is_file():
        raise ValueError("Build the dashboard first: cd web; npm run build")
    data = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):
            pass

        def send_head(self):
            if urlsplit(self.path).path == "/snapshot.json":
                import io
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return io.BytesIO(data)
            return super().send_head()

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            super().end_headers()

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve_preview(snapshot_path: Path, web_root: Path, port: int):
    with preview_server(snapshot_path, web_root, port) as server:
        print(f"Private dashboard: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return {"preview": "stopped", "public_snapshot_changed": False}
