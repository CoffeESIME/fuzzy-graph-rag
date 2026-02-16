import weaviate
import os
import json
import sys

# Add backend to path to import config if needed, but let's try direct connection first
# Assuming default localhost:8080 based on previous context

def check_weaviate():
    print("🔌 Connecting to Weaviate at localhost:8080...")
    
    try:
        client = weaviate.Client(
            url="http://localhost:8080",
            # auth_client_secret=weaviate.AuthApiKey(api_key="YOUR_API_KEY"), # If needed
        )
        
        if not client.is_ready():
            print("❌ Weaviate is NOT ready.")
            return

        print("✅ Weaviate is ready.")
        
        meta = client.get_meta()
        print(f"ℹ️  Version: {meta.get('version')}")
        
        print("\n📂 Schemas (Collections):")
        schema = client.schema.get()
        classes = schema.get('classes', [])
        
        if not classes:
            print("   ⚠️ No classes found in schema.")
        else:
            for cls in classes:
                print(f"   - {cls['class']} ({cls.get('vectorizer', 'none')})")
                props = cls.get('properties', [])
                print(f"     Properties: {[p['name'] for p in props]}")
                
        # Check specific collections we expect
        expected = ["TextSpace", "VisualSpace", "AudioSpace", "MemorySpace"]
        existing = [c['class'] for c in classes]
        
        print("\n🔍 Missing Collections:")
        for e in expected:
            if e not in existing:
                print(f"   ❌ {e} is MISSING")
            else:
                print(f"   ✅ {e} exists")
                
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_weaviate()
