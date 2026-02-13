
import sys
import os

# Ensure we can import from the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.clients import get_minio_client
from config.settings import get_settings

def list_files():
    try:
        settings = get_settings()
        client = get_minio_client()
        bucket_name = "rag-dataset"
        
        print(f"Listing objects in {bucket_name}...")
        
        # List objects
        paginator = client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name)
        
        count = 0
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    print(f"KEY: {obj['Key']} | SIZE: {obj['Size']}")
                    count += 1
        
        print(f"Total objects found: {count}")
            
    except Exception as e:
        print(f"Error listing MinIO objects: {e}")

if __name__ == "__main__":
    list_files()
