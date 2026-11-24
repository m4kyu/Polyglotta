import hashlib
import secrets
import time
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import select

from .db_session import DB
from .models import Account, LoginSession

COOKIE = "__Host-polyglotta"
LIFETIME = 7 * 86400
hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


class PasswordInput(BaseModel):
    password: SecretStr

    @field_validator("password")
    @classmethod
    def check_length(cls, value):
        if not 15 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Use a password of 15 to 128 characters.")
        return value


class Credentials(PasswordInput):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def matches(encoded: str, password: str):
    try:
        return hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False


def current_account(request: Request, db: DB):
    token = request.cookies.get(COOKIE, "")
    account = db.scalar(select(Account).join(LoginSession).where(
        LoginSession.digest == digest(token), LoginSession.expires > int(time.time())))
    if account is None:
        raise HTTPException(401, "Sign in to continue.")
    return account


User = Annotated[Account, Depends(current_account)]
