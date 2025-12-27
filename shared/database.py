from sqlmodel import SQLModel, create_engine, Session
from config.settings import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, echo=True if settings.ENV_STATE == "dev" else False)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
