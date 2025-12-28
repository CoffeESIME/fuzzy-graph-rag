import boto3
import weaviate
import redis
from neo4j import GraphDatabase, Driver
from config.settings import get_settings
from functools import lru_cache
from botocore.exceptions import ClientError

settings = get_settings()

@lru_cache()
def get_minio_client():
    """
    Returns a Boto3 S3 client configured for MinIO.
    Checks if the 'rag-dataset' bucket exists, creating it if not.
    """
    endpoint = settings.MINIO_ENDPOINT
    if not endpoint.startswith("http"):
        endpoint = f"http://{endpoint}"

    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        use_ssl=settings.MINIO_SECURE
    )
    
    bucket_name = "rag-dataset"
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError:
        # If the bucket does not exist or we don't have access, try to create it
        try:
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")
        except Exception as e:
            print(f"Failed to create bucket '{bucket_name}': {e}")
            # Depending on requirements, we might want to raise here or just return the client
            # expecting the caller to handle it. For now, we return the client.
    
    return s3_client

@lru_cache()
def get_weaviate_client() -> weaviate.WeaviateClient:
    """
    Returns a Weaviate v4 client connected to the custom host/port.
    """
    # Parse the host from URL if it contains http/https, or use it directly
    host = settings.WEAVIATE_URL.replace("http://", "").replace("https://", "")
    
    client = weaviate.connect_to_custom(
        http_host=host,
        http_port=settings.WEAVIATE_PORT,
        http_secure=False, # Assuming internal network, add setting if needed
        grpc_host=host,
        grpc_port=settings.WEAVIATE_GRPC_PORT,
        grpc_secure=False
    )
    return client

@lru_cache()
def get_neo4j_driver() -> Driver:
    """
    Returns a Neo4j driver instance.
    """
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    return driver

@lru_cache()
def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client instance.
    """
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )
