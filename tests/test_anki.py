import json
from unittest import TestCase
from tempfile import TemporaryDirectory
from pathlib import Path
from fastapi.testclient import TestClient
from polyglotta.application import create_app


class AnkiIsolationTests(TestCase):
    def test_mapping_export_and_account_cleanup(self):
        with TemporaryDirectory() as folder:
            app = create_app(Path(folder)/"db")
            with TestClient(app, base_url="https://test", headers={"Origin":"http://127.0.0.1:8000"}) as client:
                def create(name):
                    client.post("/api/auth/register", json={"username":name,"password":"long password sample"}).raise_for_status()
                    return client.post("/api/languages",json={"name":"French"}).json()["id"]
                first = create("first")
                second = client.post("/api/languages",json={"name":"Spanish"}).json()["id"]
                path = f"/api/languages/{first}"
                card = client.post(path+"/cards",json={"front":"a","back":"b"}).json()["id"]
                snapshot = {"today":"2026-11-24","decks":[{"id":1,"name":"French"},{"id":2,"name":"French::Food"}],
                            "reviews":[[2,"2026-11-24",3,2,9000]]}
                with app.state.engine.begin() as db:
                    db.exec_driver_sql("INSERT INTO anki_links(account_id,generation,snapshot,updated) VALUES(1,'gen',?,1)",(json.dumps(snapshot),))
                client.put(path+"/anki/decks",json={"decks":[1]}).raise_for_status()
                self.assertEqual(client.put(f"/api/languages/{second}/anki/decks",json={"decks":[2]}).status_code,409)
                progress=client.get(path+"/anki?days=180").json()
                self.assertEqual(len(progress["days"]),180)
                progress=client.get(path+"/anki").json()
                self.assertEqual(progress["days"]["2026-11-24"],[0,0,2,0,9000])
                self.assertTrue(progress["stale"])
                for _ in range(2):
                    client.post(path+f"/cards/{card}/anki",json={"deck":2}).raise_for_status()
                cookie=client.cookies.get("__Host-polyglotta")
                client.cookies.clear()
                create("second")
                self.assertFalse(client.get("/api/anki").json()["linked"])
                self.assertEqual(client.get(path+"/anki").status_code,404)
                client.cookies.clear()
                client.cookies.set("__Host-polyglotta",cookie)
                client.request("DELETE","/api/account",json={"password":"long password sample"}).raise_for_status()
                with app.state.engine.connect() as db:
                    self.assertEqual(db.exec_driver_sql("SELECT * FROM anki_cleanup").all(),[(1,)])
                    self.assertEqual(db.exec_driver_sql("SELECT * FROM anki_exports").all(),[])
                    self.assertEqual(db.exec_driver_sql("SELECT ready FROM anki_gate").scalar(),0)
