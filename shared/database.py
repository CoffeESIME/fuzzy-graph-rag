from sqlmodel import SQLModel, Session, create_engine
from config.settings import get_settings
from typing import Generator

settings = get_settings()

# Create the database engine
# echo=True can be useful for debugging, but keeping it off for production-like feel by default unless needed
engine = create_engine(settings.DATABASE_URL, echo=False)

def get_session() -> Generator[Session, None, None]:
    """
    Dependency generator for FastAPI to get a SQLModel Session.
    """
    with Session(engine) as session:
        yield session

def init_db():
    """
    Utility to create tables if they don't exist.
    """
    SQLModel.metadata.create_all(engine)
