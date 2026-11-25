import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import insert

from polyglotta import anki_service
from polyglotta.anki_provisioning import provisioning_server
from polyglotta.application import create_app
from polyglotta.models import AnkiCleanup


class ConnectTests(TestCase):
    def setUp(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, POLYGLOTTA_ANKI_SOCKET=str(folder / "link.sock"),
                                     POLYGLOTTA_ANKI_URL="https://sync.example.org/"))
        self.enterContext(patch.object(anki_service, "ROOT", folder))
        self.app = create_app(folder / "journal")
        self.client = self.enterContext(TestClient(self.app, base_url="https://test",
            headers={"Origin": "http://127.0.0.1:8000"}))

    def start_provisioning(self):
        self.enterContext(provisioning_server(
            lambda uid, **fields: anki_service.provision(self.app.state.engine, "link", account_id=uid, **fields)
        ))

    def register(self, name):
        self.client.cookies.clear()
        self.client.post("/api/auth/register", json={
            "username": name, "password": "long password sample"
        }).raise_for_status()

    def test_access_and_availability(self):
        self.assertEqual(self.client.post("/api/anki/connect").status_code, 401)
        self.register("one")
        self.assertEqual(self.client.post("/api/anki/connect", headers={"Origin": "https://other"}).status_code, 403)
        self.assertEqual(self.client.post("/api/anki/connect").status_code, 503)
        self.assertFalse(self.client.get("/api/anki").json()["linked"])
        self.start_provisioning()
        with self.app.state.engine.begin() as db:
            db.execute(insert(AnkiCleanup).values(account_id=1))
        self.assertEqual(self.client.post("/api/anki/connect").status_code, 409)

    def test_concurrent_signup_and_account_isolation(self):
        self.start_provisioning()
        self.register("one")
        with ThreadPoolExecutor(2) as pool:
            requests = [pool.submit(self.client.post, "/api/anki/connect") for _ in range(2)]
            responses = sorted((req.result() for req in requests), key=lambda r: r.status_code)
        self.assertEqual([r.status_code for r in responses], [201, 409])
        credentials = responses[0].json()
        self.assertEqual(credentials["username"], "p1")
        self.assertTrue(credentials["password"])
        self.assertEqual(responses[0].headers["Cache-Control"], "no-store")
        self.assertNotIn("password", self.client.get("/api/anki").json())
        self.register("two")
        self.assertFalse(self.client.get("/api/anki").json()["linked"])
        result = self.client.post("/api/anki/connect", json={"account_id": 1, "username": "learner", "password": "custom sync password"})
        self.assertEqual(result.json()["username"], "learner")

    def test_custom_credentials_and_reuse(self):
        self.start_provisioning()
        self.register("one")
        credentials = {"username": "study_One", "password": "private sync password"}
        url = "/api/anki/connect"
        bad = self.client.post(url, json={**credentials, "username": "p2"})
        self.assertEqual(bad.status_code, 409)
        bad = self.client.post(url, json={**credentials, "password": "short-secret"})
        self.assertEqual(bad.status_code, 422)
        self.assertNotIn("short-secret", bad.text)
        result = self.client.post(url, json=credentials)
        self.assertEqual(result.status_code, 201)
        self.assertNotIn("password", result.json())
        self.assertEqual(self.client.get("/api/anki").json()["username"], "study_One")
        self.register("two")
        credentials["username"] = "study_one"
        self.assertEqual(self.client.post(url, json=credentials).status_code, 409)
        anki_service.provision(self.app.state.engine, "revoke", "one")
        self.assertEqual(self.client.post(url, json=credentials).status_code, 409)
