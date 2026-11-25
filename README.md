# Polyglotta

A private learner journal with a separate dashboard, activity history, and flashcard deck for each language.

## Run locally

With Python 3.10 or newer, run these commands from the project directory.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app
```

Open http://127.0.0.1:8000 and create an account, then select **Add language**. For a YouTube video, paste its link in **Source URL** to fill the title and viewing time automatically. Adjust the minutes for a partial session. If the video details are unavailable, you can enter them manually. Use **Activity history** to edit a session or create a flashcard from its source.

SQLite stores your records in `data/polyglotta.sqlite3`. Set `POLYGLOTTA_DB` to use another database path. The browser remembers each profile’s active language. Open **Account** to sign out or permanently delete your profile with your current password. Use a password manager to retain your credentials. This release has no password reset flow.

## Hosting and existing journals

Run a single application host with persistent SQLite storage and restrict the database and backups to the service operator. Serve the UI and API on the same HTTPS origin behind a TLS reverse proxy. Set `POLYGLOTTA_ORIGIN` to the exact external origin (for example `https://journal.example.com`, without a trailing slash). Bind Uvicorn privately and set `--forwarded-allow-ips` to the proxy address. Configure the proxy to overwrite forwarded client IP headers, cap request bodies, and keep cookies and request bodies out of logs. Browser writes must include the matching Origin header. The default origin supports local development at the exact loopback URL above.

Before upgrading, stop the old server and use SQLite’s backup command to create a protected backup. Rehearse the upgrade against a copy using `POLYGLOTTA_DB`. Startup migrates the old journal to an inaccessible owner account. On the host, run the following against the intended database to choose the owner's username and password.

```sh
.venv/bin/python -m polyglotta.claim_journal
```

Sign in and check the original languages, sessions and cards before enabling public traffic. Fresh installations need no owner setup. To roll back, stop the new service and restore the pre-upgrade backup with the previous application version. Define a backup expiry policy and prevent restored backups from reactivating deleted accounts or previously issued sessions.

Interactive API documentation is available at http://127.0.0.1:8000/docs.

## Explore the demo

Select **Explore demo** on the empty dashboard or in the language menu. Switch between **Spanish (demo)** and **Japanese (demo)** to compare their immersion calendars, browse sample reading and watching sessions, and practice four phrase cards in each language. Session dates are relative to the first time you open the demo. Reopening it keeps your edits and practice material.

## Backend architecture

`main:app` loads the FastAPI application factory from `polyglotta.application`. Routes handle HTTP validation and responses using Pydantic schemas. SQLAlchemy models describe the journal tables. Each request gets its own synchronous session, and the demo and statistics services contain the logic shared across multiple records. SQLite write transactions reserve the writer before checking existing records, including during concurrent demo requests.

Startup runs Alembic against the configured database. The baseline recognizes both original journal schemas, including the version created before demo support. Subsequent schema changes belong in a new revision under `migrations/versions`. Use `.venv/bin/alembic current` to inspect the revision and `.venv/bin/alembic revision --autogenerate -m "description"` to draft a migration after changing models. Review generated revisions before applying them.

Run the migration regression tests with `.venv/bin/python -m unittest discover -s tests`.

## Anki Desktop and AnkiDroid sync

Polyglotta can run the official Anki sync server on the same Linux host. Devices sync collections and media with that server. A separate client replica publishes per-language review statistics and sends phrase cards. Web-only installations can omit the service.

1. Back up the journal and start the updated web app to apply the migration. In the project directory create a dedicated environment with `python -m venv .anki-venv` and `.anki-venv/bin/pip install -r requirements-anki.txt`. Alternatively use a system Python with Anki 26.09.4 installed. Run the operator and service commands from the project directory.
2. Set `POLYGLOTTA_DB` to the same absolute journal path in both services. In the Anki service and operator shell set `POLYGLOTTA_ANKI_DIR` to a private persistent directory owned by the service user. The web process needs the journal and access to the local provisioning socket. With the supplied systemd unit, set `POLYGLOTTA_ANKI_SOCKET=/run/polyglotta-anki/provision.sock` on the web process and give its service user membership in the socket directory’s group. The service owns the directory (0750) and socket (0660). Keep the Anki data directory private. For a same-user development setup, both processes default to `POLYGLOTTA_ANKI_DIR/provision.sock`. Set `POLYGLOTTA_ANKI_URL=https://anki.example.org/` on the web app. Configure the Anki service's `TZ` to the study timezone used by the installation.
3. Configure DNS and TLS for the dedicated sync hostname. Include [the Nginx locations](deploy/anki.nginx.conf) inside that TLS server block. The readiness subrequest closes public access immediately during credential changes or deletion. Keep port 8081 on loopback. Adapt the paths and user in [the systemd unit](deploy/polyglotta-anki.service), install it, and start it. For a foreground run use `.anki-venv/bin/python -m polyglotta.anki_service serve`.
4. Sign in and choose **Account → Anki → Connect**. Choose a unique sync username and a password of 15 to 128 characters. Use these credentials in Anki. Each learner can connect their own profile once the supervisor is running. Operators can also run `.anki-venv/bin/python -m polyglotta.anki_service link USERNAME` locally. Use `rotate USERNAME` to replace credentials. **Revoke removes hosted data**. The command `revoke USERNAME` disconnects the profile and queues deletion of the collection, media, replica and credentials. Account deletion does the same. Keep the supervisor running to finish cleanup. Device copies and retained host backups have separate lifetimes.
5. On the device holding the complete collection, make a backup, configure the custom server URL in sync preferences, sign in using the separate credentials and upload on first sync. Set the same endpoint on the other device and choose download. On AnkiDroid use the custom sync server setting (modern versions accept a single base URL). See [Anki’s self-hosting manual](https://docs.ankiweb.net/manual/sync-server). Upgrade the server and clients together after checking compatibility.

After first sync, open a language dashboard and select **Map decks**. Selecting a parent includes descendants. Current home deck determines review attribution, including cards temporarily in filtered decks. The chart uses actual answer buttons and recorded study time at the collection's day rollover in the service timezone. Its 7/30-day range follows the dashboard range. The last successful snapshot remains visible during outages.

Choose **Send to Anki** on a phrase card, select the destination if prompted, then sync the receiving device. Export uses a single-template normal note type with Front and Back fields (the standard Basic type qualifies). Later journal edits and deletions do not modify the exported note. A requested full sync pauses the worker. Back up and reconcile the authoritative collection on a device first, finish syncing it, then run `resume USERNAME`. This archives the worker replica and downloads the server collection again. Back up the journal and Anki data directory together with both services stopped.

For the real-server integration check, run `.anki-venv/bin/python tests/anki_roundtrip.py` from the project root with the web dependencies installed in `.venv`. It uses temporary profiles and an ephemeral loopback port to check two clients, media transfer, reviews, export retries, worker restart and revocation.

The integration check was exercised with Anki's 26.09.4 desktop sync engine. Before opening the hosted endpoint to learners, verify login, initial download, one review, and media sync on the intended AnkiDroid and desktop application versions. Device UI compatibility and the public TLS/proxy configuration require a check on the deployment.
