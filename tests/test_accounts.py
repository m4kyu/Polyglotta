import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from polyglotta.application import create_app
from polyglotta.security import COOKIE, digest

ORIGIN = "https://journal.test"
PASSWORD = "a long private passphrase"
LANG = "/api/languages"


class AccountTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch.dict(os.environ, POLYGLOTTA_ORIGIN=ORIGIN):
            app = create_app(Path(temp.name) / "journal.db")
        self.client = self.enter_client(app)
        self.engine = app.state.engine

    def enter_client(self, app):
        client = TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN})
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client

    def auth(self, action, name, password=PASSWORD):
        return self.client.post("/api/auth/" + action, json={"username": name, "password": password})

    def rows(self, sql):
        with self.engine.connect() as conn:
            return conn.exec_driver_sql(sql).all()

    def test_isolation_and_deletion(self):
        client = self.client
        self.assertEqual(client.get(LANG).status_code, 401)
        self.assertEqual(client.get("/api/youtube/jNQXAC9IVRw").status_code, 401)
        demo = LANG + "/demo?today=2025-02-28"
        self.auth("register", "Alice").raise_for_status()
        alice = client.post(demo).json()["language_id"]
        client.post(LANG, json={"name": "Japanese"}).raise_for_status()
        first_session = client.cookies.get(COOKIE)
        client.cookies.clear()
        self.auth("register", "Bob").raise_for_status()
        self.assertEqual(client.get(LANG).json(), [])
        client.post(LANG, json={"name": "Japanese"}).raise_for_status()
        bob = client.post(demo).json()["language_id"]
        self.assertNotEqual(alice, bob)
        bob_session = client.cookies.get(COOKIE)
        path = f"{LANG}/{alice}"
        for collection, data in (("cards", {"front": "a", "back": "b"}),
                                 ("activities", {"kind": "video", "title": "a",
                                                 "day": "2025-01-01", "minutes": 1})):
            url = path + "/" + collection
            for response in (client.get(url), client.post(url, json=data),
                             client.put(url + "/1", json=data), client.delete(url + "/1")):
                self.assertEqual(response.status_code, 404)
        self.assertEqual(client.get(path + "/statistics?today=2025-02-28").status_code, 404)
        client.cookies.clear()
        self.auth("login", "ALICE").raise_for_status()
        hashes = [row[0] for row in self.rows("SELECT password_hash FROM accounts")]
        self.assertTrue(all(h.startswith("$argon2id$") for h in hashes))
        self.assertNotEqual(*hashes)
        self.assertIn((digest(first_session),), self.rows("SELECT digest FROM login_sessions"))
        def remove(password):
            return client.request("DELETE", "/api/account", json={"password": password})
        self.assertEqual(remove("another long password").status_code, 403)
        self.assertEqual(remove(PASSWORD).status_code, 204)
        client.cookies.set(COOKIE, first_session)
        self.assertEqual(client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.rows("SELECT username FROM accounts"), [("Bob",)])
        self.assertEqual(self.rows("SELECT digest FROM login_sessions"), [(digest(bob_session),)])
        self.assertEqual(self.rows("PRAGMA foreign_key_check"), [])
        client.cookies.clear()
        client.cookies.set(COOKIE, bob_session)
        self.assertEqual(len(client.get(f"{LANG}/{bob}/cards").json()), 4)

    def test_security_controls(self):
        data = {"username": "learner", "password": PASSWORD}
        for origin in ("", "https://other.test"):
            r = self.client.post("/api/auth/register", json=data, headers={"Origin": origin})
            self.assertEqual(r.status_code, 403)
        invalid = self.auth("register", "invalid user")
        self.assertEqual(invalid.status_code, 422)
        self.assertNotIn(PASSWORD, invalid.text)
        r = self.auth("register", "learner")
        for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
            self.assertIn(flag, r.headers["set-cookie"])
        self.assertEqual(r.headers["cache-control"], "no-store")
        token = self.client.cookies.get(COOKIE)
        self.client.post("/api/auth/logout").raise_for_status()
        self.client.cookies.set(COOKIE, token)
        self.assertEqual(self.client.get(LANG).status_code, 401)
        self.client.cookies.clear()
        self.auth("login", "learner").raise_for_status()
        with self.engine.begin() as conn:
            conn.exec_driver_sql("UPDATE login_sessions SET expires=0")
        self.assertEqual(self.client.get(LANG).status_code, 401)
        wrong = self.auth("login", "learner", PASSWORD + "x")
        for _ in range(10):
            unknown = self.auth("login", "absent")
            self.assertEqual((unknown.status_code, unknown.json()), (401, wrong.json()))
        self.assertEqual(self.auth("login", "absent").status_code, 429)

    def test_concurrent_registration(self):
        with ThreadPoolExecutor(2) as pool:
            codes = list(pool.map(lambda name: self.auth("register", name).status_code, ["One", "ONE"]))
        self.assertEqual(sorted(codes), [201, 409])
