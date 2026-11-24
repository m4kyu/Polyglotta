import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sqlalchemy import inspect

from polyglotta.database import make_engine, migrate

# Original schema and representative data, independent of current ORM metadata.
LEGACY = """
CREATE TABLE languages (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE activities (
    id INTEGER PRIMARY KEY, language_id INTEGER NOT NULL REFERENCES languages(id),
    kind TEXT NOT NULL, title TEXT NOT NULL, day TEXT NOT NULL, minutes INTEGER NOT NULL, url TEXT);
CREATE INDEX activity_history ON activities(language_id, day, id);
CREATE TABLE cards (
    id INTEGER PRIMARY KEY, language_id INTEGER NOT NULL REFERENCES languages(id),
    front TEXT NOT NULL, back TEXT NOT NULL, url TEXT);
INSERT INTO languages VALUES (9, 'Japanese');
INSERT INTO activities VALUES (7, 9, 'article', 'Tea', '2025-02-28', 15, NULL);
INSERT INTO cards VALUES (4, 9, '茶', 'tea', NULL);
"""
DEMO_TABLE = """
CREATE TABLE demo_journals (language_id INTEGER PRIMARY KEY REFERENCES languages(id));
INSERT INTO demo_journals VALUES (9);
"""


class MigrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "journal.db"
        self.engine = make_engine(self.path)
        self.addCleanup(self.engine.dispose)

    def setup_legacy(self, script):
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(script)

    def snapshot(self):
        with closing(sqlite3.connect(self.path)) as db:
            return list(db.iterdump())

    def verify_adoption(self, script):
        self.setup_legacy(script)
        before = self.snapshot()
        migrate(self.engine)
        after = self.snapshot()
        self.assertTrue(set(before).issubset(after))
        self.assertIn("demo_journals", inspect(self.engine).get_table_names())
        migrate(self.engine)
        self.assertEqual(self.snapshot(), after)

    def test_original_journal(self):
        self.verify_adoption(LEGACY)

    def test_journal_with_demo(self):
        self.verify_adoption(LEGACY + DEMO_TABLE)

    def test_incompatible_journal_remains_intact(self):
        self.setup_legacy(LEGACY.replace(" COLLATE NOCASE", ""))
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "Incompatible"):
            migrate(self.engine)
        self.assertEqual(self.snapshot(), before)
