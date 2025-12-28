import sys
import os
from typing import Optional

# Ensure we can import from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.clients import get_minio_client, get_weaviate_client, get_neo4j_driver
from shared.database import get_session, engine
from sqlmodel import SQLModel, Field, Session, select
import weaviate.classes.config as wvc

# --- POSTGRES MODEL ---
class TestModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message: str

def test_minio():
    print("\n--- Testing MinIO Write ---")
    try:
        client = get_minio_client()
        bucket_name = "rag-dataset"
        content = "Hello NAS! This is a test file."
        client.put_object(
            Bucket=bucket_name,
            Key="hello_nas.txt",
            Body=content.encode("utf-8")
        )
        print("✅ SUCCESS: Uploaded 'hello_nas.txt' to bucket 'rag-dataset'.")
    except Exception as e:
        print(f"❌ FAILED: {e}")

def test_neo4j():
    print("\n--- Testing Neo4j Write ---")
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run("MERGE (n:TestNode {message: 'Hello NAS'}) RETURN n.message AS msg")
            msg = result.single()["msg"]
            print(f"✅ SUCCESS: Created/Merged node with message: '{msg}'")
    except Exception as e:
        print(f"❌ FAILED: {e}")

def test_weaviate():
    print("\n--- Testing Weaviate Write ---")
    try:
        client = get_weaviate_client()
        collection_name = "TestObject"
        
        # Ensure collection exists
        if not client.collections.exists(collection_name):
            client.collections.create(
                name=collection_name,
                properties=[
                    wvc.Property(name="message", data_type=wvc.DataType.TEXT)
                ]
            )
            print(f"Created collection '{collection_name}'")
        
        collection = client.collections.get(collection_name)
        uuid = collection.data.insert({
            "message": "Hello NAS from Weaviate"
        })
        print(f"✅ SUCCESS: Inserted object into '{collection_name}' with UUID: {uuid}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    finally:
        # Don't close the client here if it's cached/singleton, but usually v4 client manages itself well.
        # If we wanted to close it: client.close()
        pass

def test_postgres():
    print("\n--- Testing Postgres Write ---")
    try:
        # Create table
        SQLModel.metadata.create_all(engine)
        
        with Session(engine) as session:
            test_obj = TestModel(message="Hello NAS from Postgres")
            session.add(test_obj)
            session.commit()
            session.refresh(test_obj)
            print(f"✅ SUCCESS: Saved record to Postgres with ID: {test_obj.id}")
            
    except Exception as e:
        print(f"❌ FAILED: {e}")

def cleanup():
    """Explicitly close shared connections to avoid ResourceWarnings"""
    print("\n🧹 Cleaning up connections...")
    try:
        get_weaviate_client().close()
        print("   ✅ Weaviate client closed.")
    except Exception as e:
        print(f"   ⚠️ Error closing Weaviate client: {e}")
        
    try:
        get_neo4j_driver().close()
        print("   ✅ Neo4j driver closed.")
    except Exception as e:
        print(f"   ⚠️ Error closing Neo4j driver: {e}")

if __name__ == "__main__":
    try:
        print("Starting Write Verification Script...")
        test_minio()
        test_neo4j()
        test_weaviate()
        test_postgres()
        print("\nVerification Completed.")
    finally:
        cleanup()
