"""Activate the migrated journal from the host terminal."""
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import database_path, make_engine, migrate
from .models import Account
from .security import Credentials, hasher


def claim(engine, credentials):
    with Session(engine) as db:
        db.connection(execution_options={"sqlite_write": True})
        owner = db.scalar(select(Account).where(Account.username.is_(None)))
        if owner is None:
            raise ValueError("There is no unclaimed journal.")
        if db.scalar(select(Account.id).where(Account.username == credentials.username)):
            raise ValueError("Username unavailable.")
        owner.username = credentials.username
        owner.password_hash = hasher.hash(credentials.password.get_secret_value())
        db.commit()


def main():
    engine = make_engine(database_path())
    try:
        migrate(engine)
        username = input("Owner username: ")
        password = getpass("Password: ")
        if password != getpass("Confirm password: "):
            raise ValueError("Passwords differ.")
        claim(engine, Credentials(username=username, password=password))
        print("Journal claimed.")
    except ValidationError:
        raise SystemExit("Use a valid username and a password of 15 to 128 characters.") from None
    except ValueError as error:
        raise SystemExit(str(error)) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
