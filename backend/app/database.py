from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str):
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    else:
        # Supabase Transaction Pooler (PgBouncer) does not support named
        # prepared statements across pooled connections. psycopg enables
        # them by default, so disable them for PostgreSQL connections.
        connect_args = {"prepare_threshold": None}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
