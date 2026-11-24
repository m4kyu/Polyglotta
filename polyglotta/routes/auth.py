import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select

from ..db_session import DB
from ..models import Account, Attempt, LoginSession
from ..security import (COOKIE, LIFETIME, Credentials, PasswordInput, User, digest,
                        dummy_hash, hasher, matches)

router = APIRouter(prefix="/api", tags=["Accounts"])


def charge(db, limits):
    """Count attempts inside the request's SQLite write transaction."""
    now = int(time.time())
    db.execute(delete(Attempt).where(Attempt.expires <= now))
    for key, maximum in limits:
        attempt = db.get(Attempt, digest(key))
        if attempt is None:
            db.add(Attempt(key=digest(key), count=1, expires=now + 900))
        elif attempt.count >= maximum:
            raise HTTPException(429, "Too many attempts. Try again later.",
                                headers={"Retry-After": str(attempt.expires - now)})
        else:
            attempt.count += 1


def profile(account):
    return {"id": account.id, "username": account.username}


def sign_in(db, request, response, account):
    now = int(time.time())
    old = digest(request.cookies.get(COOKIE, ""))
    db.execute(delete(LoginSession).where(
        (LoginSession.expires <= now) | (LoginSession.digest == old)))
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(digest=digest(token), account_id=account.id, expires=now + LIFETIME))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=LIFETIME, secure=True,
                        httponly=True, samesite="lax", path="/")
    return profile(account)


@router.post("/auth/register", status_code=201)
def register(data: Credentials, request: Request, response: Response, db: DB):
    charge(db, [(f"register:{request.client.host}", 10)])
    if db.scalar(select(Account.id).where(Account.username == data.username)):
        db.commit()
        raise HTTPException(409, "Username unavailable.")
    account = Account(username=data.username, password_hash=hasher.hash(data.password.get_secret_value()))
    db.add(account)
    db.flush()
    return sign_in(db, request, response, account)


@router.post("/auth/login")
def login(data: Credentials, request: Request, response: Response, db: DB):
    charge(db, [(f"ip:{request.client.host}", 50), (f"user:{data.username.lower()}", 10)])
    account = db.scalar(select(Account).where(Account.username == data.username))
    password = data.password.get_secret_value()
    if not matches(account.password_hash if account else dummy_hash, password) or account is None:
        db.commit()
        raise HTTPException(401, "Invalid username or password.")
    if hasher.check_needs_rehash(account.password_hash):
        account.password_hash = hasher.hash(password)
    return sign_in(db, request, response, account)


@router.get("/auth/me")
def me(user: User):
    return profile(user)


def signed_out():
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="lax")
    return response


@router.post("/auth/logout")
def logout(request: Request, db: DB):
    db.execute(delete(LoginSession).where(LoginSession.digest == digest(request.cookies.get(COOKIE, ""))))
    db.commit()
    return signed_out()


@router.delete("/account", status_code=204)
def remove(data: PasswordInput, request: Request, db: DB, user: User):
    charge(db, [(f"ip:{request.client.host}", 50), (f"user:{user.username.lower()}", 10)])
    if not matches(user.password_hash, data.password.get_secret_value()):
        db.commit()
        raise HTTPException(403, "Incorrect password.")
    db.delete(user)
    db.commit()
    return signed_out()
