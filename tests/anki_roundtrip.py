"""Run from the repository root with the pinned Anki Python interpreter."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
root = Path(__file__).resolve().parents[1]
from anki.collection import Collection
def full(col,auth,upload):
    col.close_for_full_sync()
    col.full_upload_or_download(auth=auth,server_usn=None,upload=upload)
    col.reopen(after_full_sync=True)
def wait(fn):
    for _ in range(120):
        result=fn()
        if result:return result
        time.sleep(.25)
    raise RuntimeError("Timed out: "+str(fn))
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]

with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(POLYGLOTTA_DB=tmp+"/journal.db",POLYGLOTTA_ANKI_DIR=tmp+"/anki",POLYGLOTTA_ANKI_PORT=str(port),RUST_LOG="error")
    subprocess.run([str(root/".venv/bin/python"),"-c","from polyglotta.database import database_path, make_engine, migrate; migrate(make_engine(database_path()))"],check=True)
    db=sqlite3.connect(os.environ["POLYGLOTTA_DB"])
    endpoint = f"http://127.0.0.1:{port}/"
    os.environ["POLYGLOTTA_ANKI_URL"] = endpoint
    cli=[sys.executable,"-m","polyglotta.anki_service"]
    svc=subprocess.Popen(cli+["serve"])
    try:
        wait(lambda: (Path(tmp)/"anki"/"provision.sock").is_socket())
        signup = """
import json
from fastapi.testclient import TestClient
from polyglotta.application import create_app
with TestClient(create_app(), base_url='https://test', headers={'Origin':'http://127.0.0.1:8000'}) as client:
    client.post('/api/auth/register', json={'username':'test','password':'long password sample'}).raise_for_status()
    response = client.post('/api/anki/connect', json={'username':'learner_one','password':'my own sync password'})
    response.raise_for_status()
    print(json.dumps(response.json()))
"""
        credentials = json.loads(subprocess.check_output([str(root/".venv/bin/python"), "-c", signup]))
        db.execute("insert into languages(name,account_id) values('French',1)")
        db.execute("insert into cards(language_id,front,back) values(1,'Hello','Bonjour')")
        db.commit()
        wait(lambda: db.execute("select ready from anki_gate").fetchone()[0])
        time.sleep(.8)
        def device(name):
            folder=Path(tmp)/name
            folder.mkdir()
            return Collection(str(folder/"collection.anki2"))
        a=device("desktop")
        auth=a.sync_login(credentials["username"], "my own sync password", credentials["endpoint"])
        note=a.new_note(a.models.by_name("Basic"))
        note["Front"]="Test"
        note["Back"]="Response"
        a.add_note(note,1)
        a.media.write_data("sample.txt",b"polyglotta media")
        a.sync_collection(auth,False)
        full(a,auth,True)
        def media(col):
            col.sync_media(auth)
            wait(lambda:not col.media_sync_status().active)
        media(a)
        b=device("second")
        full(b,auth,False)
        media(b)
        assert (Path(tmp)/"second"/"collection.media"/"sample.txt").read_bytes()==b"polyglotta media"
        b.sched.answerCard(b.sched.getCard(),3)
        b.sync_collection(auth,False)
        db.execute("insert into anki_exports(card_id,guid,deck,front,back) values(1,'unique-test',1,'Hello','Bonjour')")
        db.commit()
        wait(lambda: db.execute("select state from anki_exports").fetchone()[0]=="Sent")
        snap=json.loads(db.execute("select snapshot from anki_links").fetchone()[0])
        assert sum(r[3] for r in snap["reviews"])==1,snap
        a.sync_collection(auth,False)
        assert a.db.scalar("select count(*) from notes where guid='unique-test'")==1
        assert a.db.scalar("select count(*) from revlog")==1
        # Repeat a queued job as if the worker stopped between sync and acknowledgement.
        db.execute("update anki_exports set state='Queued'")
        db.commit()
        wait(lambda:db.execute("select state from anki_exports").fetchone()[0]=="Sent")
        b.sync_collection(auth,False)
        exported=b.db.scalar("select c.id from cards c join notes n on c.nid=n.id where guid='unique-test'")
        card = b.get_card(exported)
        card.start_timer()
        b.sched.answerCard(card,4)
        b.sync_collection(auth,False)
        # Restarting the service triggers its periodic snapshot immediately.
        svc.terminate();svc.wait()
        svc=subprocess.Popen(cli+["serve"])
        wait(lambda:sum(r[3] for r in json.loads(db.execute("select snapshot from anki_links").fetchone()[0])["reviews"])==2)
        a.sync_collection(auth,False)
        assert a.db.scalar("select count(*) from notes where guid='unique-test'")==1
        assert a.db.scalar("select count(*) from revlog where ease=4")==1
        a.close();b.close()
        subprocess.run(cli+["revoke","test"],check=True)
        assert not db.execute("select ready from anki_gate").fetchone()[0]
        wait(lambda: not db.execute("select 1 from anki_cleanup").fetchone())
        assert not (Path(tmp)/"anki/server/learner_one").exists()
        assert not (Path(tmp)/"anki/users/p1").exists()
        print("Two-client sync, media, rating, export and snapshot passed.")
    finally:
        svc.terminate();svc.wait()
