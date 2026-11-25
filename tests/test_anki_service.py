from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import insert, select, update
from sqlalchemy.exc import OperationalError

from polyglotta import anki_service
from polyglotta.database import make_engine, migrate
from polyglotta.models import Account, AnkiCleanup, AnkiDeckMap, AnkiExport, AnkiLink, Card, Language


class OperatorTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.enterContext(patch.object(anki_service, "ROOT", self.root))
        self.engine = make_engine(self.root / "journal")
        self.addCleanup(self.engine.dispose)
        migrate(self.engine)
        with self.engine.begin() as db:
            db.execute(insert(Account), [{"username": "first"}, {"username": "second"}])

    def provision(self, action, username="first"):
        with redirect_stdout(StringIO()):
            anki_service.provision(self.engine, action, username)

    def test_missing_database(self):
        path = self.root / "missing"
        engine = make_engine(path, existing_only=True, timeout=15)
        self.addCleanup(engine.dispose)
        with self.assertRaises(OperationalError):
            anki_service.provision(engine, "link", "first")
        self.assertFalse(path.exists())

    def test_rotate_and_resume(self):
        self.provision("link")
        with self.engine.begin() as db:
            generation = db.scalar(select(AnkiLink.generation))
            db.execute(update(AnkiLink).values(paused=1, updated=123, snapshot="{}", message="paused"))
        self.provision("rotate")
        with self.engine.connect() as db:
            link = db.execute(select(AnkiLink)).mappings().one()
        self.assertNotEqual(link["generation"], generation)
        self.assertEqual((link["paused"], link["updated"], link["snapshot"], link["message"]),
                         (1, 123, "{}", "paused"))
        self.assertFalse(anki_service.secret_path(1, generation).exists())
        secret = anki_service.secret_path(1, link["generation"])
        self.assertTrue(secret.is_file())
        for name in ("collection.anki2", "collection.anki2-wal"):
            (secret.parent / name).touch()
        self.provision("resume")
        backup, = secret.parent.glob("paused-*")
        self.assertEqual(sorted(p.name for p in backup.iterdir()), ["collection.anki2", "collection.anki2-wal"])
        with self.engine.connect() as db:
            self.assertEqual(db.execute(select(AnkiLink.paused, AnkiLink.updated, AnkiLink.message)).one(),
                             (0, None, None))

    def test_revoke_only_one_profile(self):
        for uid, name in enumerate(("first", "second"), 1):
            self.provision("link", name)
            with self.engine.begin() as db:
                db.execute(insert(Language).values(id=uid, account_id=uid, name="French"))
                db.execute(insert(Card).values(id=uid, language_id=uid, front="a", back="b"))
                db.execute(insert(AnkiDeckMap).values(language_id=uid, deck=1))
                db.execute(insert(AnkiExport).values(card_id=uid, guid=name, deck=1, front="a", back="b"))
        self.provision("revoke")
        with self.engine.connect() as db:
            for column in (AnkiLink.account_id, AnkiDeckMap.language_id, AnkiExport.card_id):
                self.assertEqual(db.scalars(select(column)).all(), [2])
            self.assertEqual(db.scalars(select(AnkiCleanup.account_id)).all(), [1])
