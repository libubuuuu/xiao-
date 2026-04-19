from __future__ import annotations

import json
import os
import shutil
import threading
import time
import urllib.request
import unittest
import uuid
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[1] / "data" / f"enterprise-tests-{uuid.uuid4().hex}"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = TEST_ROOT / "enterprise.sqlite3"

os.environ["APP_DB_PATH"] = str(TEST_DB_PATH)
os.environ["OWNER_ACCESS_TOKEN"] = "enterprise-test-token"
os.environ["HOST"] = "127.0.0.1"
os.environ["PORT"] = "0"

from backend.app.repository import ContentRepository  # noqa: E402
from backend import main  # noqa: E402


class RepositoryPersistenceTests(unittest.TestCase):
    def test_cart_item_survives_repository_reopen(self):
        repository = ContentRepository(TEST_ROOT / "repository.sqlite3")
        now = "2026-04-19T00:00:00+00:00"
        item = {
            "id": "repo-item-1",
            "platform_id": "x",
            "platform_name": "X",
            "title": "Repository smoke test",
            "summary": "Persist through reopen",
            "content_type": "text",
            "freshness": "now",
            "source_url": "https://example.com",
            "media": [],
        }

        repository.add_cart_item(item, now)
        self.assertEqual(repository.list_cart_items()[0]["id"], "repo-item-1")

        reopened = ContentRepository(TEST_ROOT / "repository.sqlite3")
        self.assertEqual(reopened.list_cart_items()[0]["id"], "repo-item-1")


class ApiSmokeTests(unittest.TestCase):
    port: int

    def _start_server(self):
        server = main.ThreadingHTTPServer(("127.0.0.1", 0), main.APIHandler)
        self.port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def _wait_ready(self):
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/health", timeout=2) as response:
                    return response.status, json.loads(response.read().decode("utf-8"))
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("backend did not become ready in time")

    def _request(self, path: str, method: str = "GET", payload: dict | None = None):
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_cart_persists_after_restart(self):
        server, thread = self._start_server()
        try:
            status, health = self._wait_ready()
            self.assertEqual(status, 200)
            self.assertTrue(health["database_exists"])

            item = {
                "id": "api-item-1",
                "platform_id": "x",
                "platform_name": "X",
                "title": "API smoke test",
                "summary": "Persist through backend restart",
                "content_type": "text",
                "freshness": "now",
                "source_url": "https://example.com",
                "media": [],
            }
            status, body = self._request("/api/cart/items", "POST", {"item": item})
            self.assertEqual(status, 200)
            self.assertEqual(body["count"], 1)

            status, body = self._request("/api/cart")
            self.assertEqual(status, 200)
            self.assertEqual(body["count"], 1)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        server2, thread2 = self._start_server()
        try:
            status, health = self._wait_ready()
            self.assertEqual(status, 200)
            self.assertEqual(health["cart_count"], 1)

            status, body = self._request("/api/cart")
            self.assertEqual(status, 200)
            self.assertEqual(body["count"], 1)
            self.assertEqual(body["items"][0]["id"], "api-item-1")
        finally:
            server2.shutdown()
            thread2.join(timeout=5)
            server2.server_close()


def tearDownModule():
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
