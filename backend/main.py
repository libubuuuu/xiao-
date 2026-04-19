from __future__ import annotations

import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

try:
    from app import store
    from app.frontend import guess_content_type, resolve_frontend_asset
    from app.server import app as starlette_app
except ImportError:  # pragma: no cover
    from backend.app import store
    from backend.app.frontend import guess_content_type, resolve_frontend_asset
    from backend.app.server import app as starlette_app

app = starlette_app


def _json(data, status=200, extra_headers=None):
    return status, data, extra_headers or {}


def _root():
    return _json(
        {
            "name": "Social Content Platform API",
            "version": "0.1.0",
            "policy": "official APIs and authorized integrations only",
            "docs": "/docs",
        }
    )


class APIHandler(BaseHTTPRequestHandler):
    server_version = "SocialContentPlatform/0.1"

    def log_message(self, format, *args):  # pragma: no cover
        return

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Owner-Token")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _write_json(self, status, data, extra_headers=None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._write_bytes(status, payload, "application/json; charset=utf-8", extra_headers)

    def _write_bytes(self, status, payload: bytes, content_type: str, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Owner-Token")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _write_file(self, file_path: Path):
        payload = file_path.read_bytes()
        content_type = guess_content_type(file_path)
        self._write_bytes(200, payload, content_type)

    def _resolve_file_path(self, base_dir: Path, request_path: str) -> Path | None:
        relative_path = request_path.lstrip("/")
        if not relative_path:
            return None

        base_root = base_dir.resolve()
        candidate = (base_dir / relative_path).resolve()
        try:
            candidate.relative_to(base_root)
        except ValueError:
            return None

        return candidate if candidate.is_file() else None

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
          return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _owner_ok(self):
        return store.validate_owner_token(self.headers.get("X-Owner-Token") or "")

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        segments = [segment for segment in path.split("/") if segment]

        if method == "GET" and path == "/":
            asset = resolve_frontend_asset(path)
            if asset is not None:
                return self._write_file(asset)
            status, data, headers = _root()
            return self._write_json(status, data, headers)

        if method == "GET" and path == "/api":
            status, data, headers = _root()
            return self._write_json(status, data, headers)

        if method == "GET" and path == "/api/meta":
            return self._write_json(
                200,
                {
                    "name": "Social Content Platform",
                    "version": "0.1.0",
                    "modules": [
                        "platform_radar",
                        "cart_workspace",
                        "remix_studio",
                        "image_canvas",
                        "publishing_center",
                        "comment_assistant",
                    ],
                    "policy": "compliant workflow only",
                },
            )

        if method == "GET" and path == "/api/overview":
            return self._write_json(200, store.get_overview())

        if method == "GET" and path == "/api/platforms":
            region = (params.get("region") or [None])[0]
            if region is not None and region not in {"domestic", "overseas"}:
                return self._write_json(400, {"detail": "region must be domestic or overseas"})
            return self._write_json(200, {"items": store.get_platforms(region)})

        if method == "GET" and path == "/api/accounts":
            if not self._owner_ok():
                return self._write_json(403, {"detail": "Owner access required"})
            platform_id = (params.get("platform_id") or [None])[0]
            return self._write_json(200, {"items": store.get_accounts(platform_id)})

        if method == "POST" and path == "/api/accounts/connect":
            if not self._owner_ok():
                return self._write_json(403, {"detail": "Owner access required"})
            payload = self._read_json()
            try:
                account = store.connect_account(
                    payload.get("platform_id", ""),
                    payload.get("display_name", ""),
                    payload.get("handle", ""),
                )
            except ValueError as exc:
                return self._write_json(400, {"detail": str(exc)})
            return self._write_json(200, {"account": account})

        if method == "GET" and path == "/api/radar":
            region = (params.get("region") or ["domestic"])[0]
            if region not in {"domestic", "overseas"}:
                return self._write_json(400, {"detail": "region must be domestic or overseas"})
            platform_id = (params.get("platform_id") or [None])[0]
            keyword = (params.get("keyword") or ["trend"])[0]
            try:
                limit = int((params.get("limit") or ["6"])[0])
            except ValueError:
                limit = 6
            limit = max(1, min(limit, 20))
            items, insights = store.build_radar_items(region, platform_id, keyword, limit)
            return self._write_json(
                200,
                {
                    "query": {
                        "region": region,
                        "platform_id": platform_id,
                        "keyword": keyword,
                        "limit": limit,
                    },
                    "items": items,
                    "insights": insights,
                },
            )

        if method == "GET" and path == "/api/cart":
            return self._write_json(200, {"items": store.STATE["cart"], "count": len(store.STATE["cart"])})

        if method == "POST" and path == "/api/cart/items":
            payload = self._read_json()
            item = payload.get("item")
            if not item:
                return self._write_json(400, {"detail": "item is required"})
            with store.LOCK:
                if not any(entry["id"] == item["id"] for entry in store.STATE["cart"]):
                    store.STATE["cart"].append(item)
            store.log_activity("add_to_cart", {"item_id": item["id"]})
            return self._write_json(200, {"items": store.STATE["cart"], "count": len(store.STATE["cart"])})

        if method == "DELETE" and len(segments) == 3 and segments[0] == "api" and segments[1] == "cart":
            item_id = segments[2]
            with store.LOCK:
                store.STATE["cart"] = [item for item in store.STATE["cart"] if item["id"] != item_id]
            store.log_activity("remove_cart_item", {"item_id": item_id})
            return self._write_json(200, {"items": store.STATE["cart"], "count": len(store.STATE["cart"])})

        if method == "POST" and path == "/api/remix/jobs":
            payload = self._read_json()
            item_ids = payload.get("item_ids") or []
            sources = [item for item in store.STATE["cart"] if item["id"] in item_ids]
            if not sources:
                return self._write_json(400, {"detail": "At least one cart item is required"})
            job = store.create_remix_job(
                {
                    "mode": payload.get("mode", "merge"),
                    "preserve_media": bool(payload.get("preserve_media", True)),
                    "tone": payload.get("tone", "professional"),
                },
                sources,
            )
            return self._write_json(200, job)

        if method == "GET" and len(segments) == 4 and segments[0] == "api" and segments[1] == "remix" and segments[2] == "jobs":
            job_id = segments[3]
            job = store.STATE["remix_jobs"].get(job_id)
            if not job:
                return self._write_json(404, {"detail": "Remix job not found"})
            return self._write_json(200, job)

        if method == "POST" and path == "/api/canvas/similar":
            payload = self._read_json()
            job = store.create_canvas_job(
                {
                    "image_name": payload.get("image_name", "uploaded-image.png"),
                    "prompt_hint": payload.get("prompt_hint", "clean, commercial, future"),
                    "count": int(payload.get("count", 6) or 6),
                    "style": payload.get("style", "editorial"),
                }
            )
            return self._write_json(200, job)

        if method == "GET" and len(segments) == 4 and segments[0] == "api" and segments[1] == "canvas" and segments[2] == "jobs":
            job_id = segments[3]
            job = store.STATE["canvas_jobs"].get(job_id)
            if not job:
                return self._write_json(404, {"detail": "Canvas job not found"})
            return self._write_json(200, job)

        if method == "POST" and path == "/api/owner/validate":
            payload = self._read_json()
            return self._write_json(200, {"valid": store.validate_owner_token(payload.get("token", ""))})

        if method == "POST" and path == "/api/publishing/drafts":
            if not self._owner_ok():
                return self._write_json(403, {"detail": "Owner access required"})
            payload = self._read_json()
            account = next((item for item in store.get_accounts() if item["id"] == payload.get("account_id")), None)
            if not account:
                return self._write_json(404, {"detail": "Account not found"})
            platform = store.get_platform(payload.get("platform_id", ""))
            if not platform:
                return self._write_json(404, {"detail": "Platform not found"})
            draft = store.create_draft(payload, account, platform)
            return self._write_json(200, {"draft": draft})

        if method == "GET" and path == "/api/publishing/drafts":
            if not self._owner_ok():
                return self._write_json(403, {"detail": "Owner access required"})
            return self._write_json(200, {"items": store.STATE["drafts"]})

        if method == "POST" and path == "/api/comments/suggestions":
            payload = self._read_json()
            job = store.create_comment_suggestions(
                {
                    "targets": payload.get("targets") or [],
                    "context": payload.get("context", ""),
                    "tone": payload.get("tone", "professional"),
                }
            )
            return self._write_json(200, job)

        if method == "GET" and path == "/api/activity":
            return self._write_json(200, {"items": store.STATE["activity_log"][-25:]})

        if method == "GET" and path == "/docs":
            return self._write_json(200, {"detail": "Open /api/meta for the product summary."})

        if path.startswith("/api/artifacts/"):
            artifact_path = self._resolve_file_path(store.ARTIFACT_DIR, path.removeprefix("/api/artifacts/"))
            if artifact_path is not None:
                return self._write_file(artifact_path)
            return self._write_json(404, {"detail": "Artifact not found"})

        if path.startswith("/api/"):
            return self._write_json(404, {"detail": "Not found"})

        if method == "GET":
            asset = resolve_frontend_asset(path)
            if asset is not None:
                return self._write_file(asset)

        return self._write_json(404, {"detail": "Not found"})


def serve(host: str = "0.0.0.0", port: int = 8000):
    server = ThreadingHTTPServer((host, port), APIHandler)
    print(f"Serving on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


if __name__ == "__main__":
    serve(host=os.getenv("HOST", "0.0.0.0"), port=_env_int("PORT", 8000))
