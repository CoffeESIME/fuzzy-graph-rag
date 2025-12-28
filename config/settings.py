import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    ENV_STATE: str = "dev"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Postgres
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Neo4j
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    
    # Weaviate
    WEAVIATE_URL: str
    WEAVIATE_PORT: int = 8080
    WEAVIATE_GRPC_PORT: int = 50051
    
    # MinIO
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('ENV_STATE', 'dev') if os.getenv('ENV_STATE') != 'prod' else 'production'}",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore' 
    )

# Logic to handle the file name selection appropriately if ENV_STATE is set before loading
# Actually, Pydantic's env_file argument is evaluated at class creation time. 
# A common pattern for dynamic env file loading:

def get_env_file():
    env_state = os.getenv("ENV_STATE", "dev") # Default to dev
    if env_state == "prod":
        return ".env.production"
    return ".env.development"

class DynSettings(Settings):
    model_config = SettingsConfigDict(
        env_file=get_env_file(),
        env_file_encoding='utf-8',
        extra='ignore'
    )

@lru_cache()
def get_settings() -> DynSettings:
    return DynSettings()
