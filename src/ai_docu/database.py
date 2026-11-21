import os
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Base(DeclarativeBase):
    pass


def normalize_database_url(database_url: str) -> str:
    scheme_separator = "://"
    if scheme_separator not in database_url:
        return database_url

    scheme, remainder = database_url.split(scheme_separator, 1)
    authority, separator, suffix = remainder.partition("/")
    if "@" not in authority:
        return database_url

    user_info, _, host_port = authority.rpartition("@")
    username, credential_separator, password = user_info.partition(":")
    if not credential_separator:
        return database_url

    encoded_user = quote(username, safe="%")
    encoded_password = quote(password, safe="%")
    normalized_authority = f"{encoded_user}:{encoded_password}@{host_port}"
    normalized_remainder = (
        f"{normalized_authority}/{suffix}" if separator else normalized_authority
    )
    return f"{scheme}{scheme_separator}{normalized_remainder}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to connect to PostgreSQL.")

    return create_engine(normalize_database_url(database_url), pool_pre_ping=True)


def get_db_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
