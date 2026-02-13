import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath("backend"))

from shared.clients import get_minio_client
from config.settings import get_settings

def list_minio_objects():
    try:
        settings = get_settings()
        client = get_minio_client()
        bucket_name = settings.MINIO_BUCKET
        
        print(f"Listing objects in bucket: {bucket_name}")
        response = client.list_objects_v2(Bucket=bucket_name, MaxKeys=20)
        
        if 'Contents' in response:
            for obj in response['Contents']:
                print(f" - {obj['Key']}")
        else:
            print("Bucket is empty or no objects found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_minio_objects()
