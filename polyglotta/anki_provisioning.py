"""Local provisioning channel shared by the web app and the Anki supervisor."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import socketserver
from threading import Thread


class LinkConflict(Exception):
    pass


def socket_path():
    directory = Path(os.environ.get("POLYGLOTTA_ANKI_DIR", "data/anki"))
    return Path(os.environ.get("POLYGLOTTA_ANKI_SOCKET", directory / "provision.sock"))


def request_link(account_id, **fields):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(20)
        client.connect(str(socket_path()))
        client.sendall(json.dumps({"id": account_id, **fields}).encode() + b"\n")
        with client.makefile("rb") as stream:
            reply = json.loads(stream.readline(2048))
    if "conflict" in reply:
        raise LinkConflict(reply["conflict"])
    return reply["username"], reply.get("password")


@contextmanager
def provisioning_server(create_link):
    class Handler(socketserver.StreamRequestHandler):
        timeout = 5

        def handle(self):
            line = self.rfile.readline(4096)
            if not line.endswith(b"\n"):
                return
            try:
                request = json.loads(line)
                fields = {key: request[key] for key in ("sync_username", "password") if key in request}
                reply = create_link(int(request["id"]), **fields)
                if fields:
                    reply.pop("password", None)
            except LinkConflict as error:
                reply = {"conflict": str(error)}
            self.wfile.write(json.dumps(reply).encode() + b"\n")

    path = socket_path()
    # The supervisor holds its instance lock and owns the socket directory.
    if path.is_socket():
        path.unlink()
    with socketserver.UnixStreamServer(str(path), Handler) as server:
        try:
            path.chmod(0o660)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield
            finally:
                server.shutdown()
                thread.join()
        finally:
            path.unlink(missing_ok=True)
