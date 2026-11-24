from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def session(request: Request):
    with Session(request.app.state.engine, expire_on_commit=False) as db:
        db.connection(execution_options={"sqlite_write": request.method != "GET"})
        yield db


DB = Annotated[Session, Depends(session)]
