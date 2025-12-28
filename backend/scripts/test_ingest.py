"""
Test script for the ingestion layer.
This script demonstrates the different upload patterns.
"""

import sys
import os

# Ensure we can import from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Asset, VectorStatus, JobStatus, VectorType
from app.schemas import UploadGroup, ProcessingOperation

def test_schema_validation():
    """Test that schemas validate correctly"""
    print("🧪 Testing Schema Validation...")
    
    # Test STANDARD operation
    standard_group = UploadGroup(
        file_indices=[0],
        operation=ProcessingOperation.STANDARD,
        vector_types=[VectorType.VISUAL_SIGLIP, VectorType.VISUAL_SEMANTIC],
        user_notes="Test image",
        discard_original=False
    )
    print(f"   ✅ STANDARD group: {standard_group.model_dump()}")
    
    # Test MERGE_OCR operation
    merge_group = UploadGroup(
        file_indices=[0, 1, 2],
        operation=ProcessingOperation.MERGE_OCR,
        vector_types=[VectorType.TEXT_CHUNK],
        user_notes="Twitter thread",
        discard_original=True
    )
    print(f"   ✅ MERGE_OCR group: {merge_group.model_dump()}")
    
    print("\n✅ All schema validations passed!\n")

def test_enum_values():
    """Test that enums have correct values"""
    print("🧪 Testing Enum Values...")
    
    # JobStatus
    assert JobStatus.ON_HOLD == "on_hold"
    assert JobStatus.PENDING == "pending"
    assert JobStatus.PROCESSING == "processing"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"
    assert JobStatus.REJECTED == "rejected"
    print("   ✅ JobStatus enum values are correct")
    
    # VectorType
    assert VectorType.VISUAL_SIGLIP == "visual_siglip"
    assert VectorType.VISUAL_SEMANTIC == "visual_semantic"
    assert VectorType.TEXT_OCR == "text_ocr"
    assert VectorType.AUDIO_CLAP == "audio_clap"
    assert VectorType.AUDIO_TRANSCRIPT == "audio_transcript"
    assert VectorType.TEXT_CHUNK == "text_chunk"
    assert VectorType.TEXT_SUMMARY == "text_summary"
    assert VectorType.USER_MEMORY == "user_memory"
    print("   ✅ VectorType enum values are correct")
    
    print("\n✅ All enum tests passed!\n")

def print_example_curl_commands():
    """Print example curl commands for testing the API"""
    print("=" * 80)
    print("📋 EXAMPLE CURL COMMANDS FOR TESTING")
    print("=" * 80)
    
    print("\n1️⃣  SINGLE FILE UPLOAD (STANDARD):")
    print("-" * 80)
    print("""
curl -X POST http://localhost:8000/ingest/upload \\
  -F "files=@test_image.jpg" \\
  -F 'upload_map=[{
    "file_indices": [0],
    "operation": "standard",
    "vector_types": ["visual_siglip", "visual_semantic"],
    "user_notes": "Test image upload",
    "discard_original": false
  }]'
""")
    
    print("\n2️⃣  MULTI-FILE MERGE (MERGE_OCR):")
    print("-" * 80)
    print("""
curl -X POST http://localhost:8000/ingest/upload \\
  -F "files=@screenshot1.png" \\
  -F "files=@screenshot2.png" \\
  -F "files=@screenshot3.png" \\
  -F 'upload_map=[{
    "file_indices": [0, 1, 2],
    "operation": "merge_ocr",
    "vector_types": ["text_chunk"],
    "user_notes": "Important Twitter thread",
    "discard_original": true
  }]'
""")
    
    print("\n3️⃣  MIXED OPERATIONS:")
    print("-" * 80)
    print("""
curl -X POST http://localhost:8000/ingest/upload \\
  -F "files=@screenshot1.png" \\
  -F "files=@screenshot2.png" \\
  -F "files=@meme.jpg" \\
  -F 'upload_map=[
    {
      "file_indices": [0, 1],
      "operation": "merge_ocr",
      "vector_types": ["text_chunk"],
      "user_notes": "Thread screenshots",
      "discard_original": true
    },
    {
      "file_indices": [2],
      "operation": "standard",
      "vector_types": ["visual_siglip", "visual_semantic", "text_ocr"],
      "user_notes": "Funny meme",
      "discard_original": false
    }
  ]'
""")
    
    print("\n" + "=" * 80)
    print("🚀 To start the server, run:")
    print("   cd backend && poetry run uvicorn app:app --reload --host 0.0.0.0 --port 8000")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 GRAPHRAG MULTIMODAL INGESTION LAYER - TEST SUITE")
    print("=" * 80 + "\n")
    
    test_enum_values()
    test_schema_validation()
    print_example_curl_commands()
    
    print("✅ All tests completed successfully!\n")
