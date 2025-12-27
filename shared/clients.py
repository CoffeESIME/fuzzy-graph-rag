import weaviate
from weaviate.connect import ConnectionParams
from neo4j import GraphDatabase
import boto3
from config.settings import get_settings

settings = get_settings()

def get_neo4j_driver():
    """
    Returns a Neo4j driver instance.
    """
    return GraphDatabase.driver(
        settings.NEO4J_URI, 
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )

def get_weaviate_client():
    """
    Returns a Weaviate v4 client.
    """
    # Adjust connection params based on environment
    return weaviate.WeaviateClient(
        connection_params=ConnectionParams.from_params(
            http_host=settings.WEAVIATE_URL,
            http_port=settings.WEAVIATE_PORT,
            http_secure=False,
            grpc_host=settings.WEAVIATE_URL,
            grpc_port=settings.WEAVIATE_GRPC_PORT,
            grpc_secure=False,
        )
    )

def get_minio_client():
    """
    Returns a boto3 client for MinIO.
    """
    return boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}", # Pydantic settings usually don't have protocol in HOST/PORT but here I defined ENDPOINT as host:port
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        use_ssl=settings.MINIO_SECURE
    )
