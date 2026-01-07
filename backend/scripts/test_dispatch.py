"""
Simple Test Script - Dispatch Task Manually
============================================

This script sends a test task directly to Celery to verify worker is processing.
"""

import sys
from app.core.celery_app import app

def main():
    print("=" * 60)
    print("  CELERY TASK DISPATCH TEST")
    print("=" * 60)
    
    # Task details
    fake_uuid = "test-uuid-12345"
    
    print(f"\n📤 Dispatching test task...")
    print(f"   Task: worker.tasks.process_vector_task")
    print(f"   Args: ['{fake_uuid}']")
    print(f"   Queue: queue_fast")
    
    try:
        # Send task
        result = app.send_task(
            'worker.tasks.process_vector_task',
            args=[fake_uuid],
            queue='queue_fast'
        )
        
        print(f"\n✅ Task dispatched successfully!")
        print(f"   Celery Task ID: {result.id}")
        print(f"   Initial State: {result.state}")
        
        print(f"\n⏳ Waiting for result (10 seconds timeout)...")
        print(f"   NOTE: This WILL fail since UUID doesn't exist in DB")
        print(f"   But you should see logs in the worker terminal!")
        
        try:
            task_result = result.get(timeout=10)
            print(f"\n✅ Task completed!")
            print(f"   Result: {task_result}")
        except Exception as e:
            print(f"\n⚠️  Task failed (expected):")
            print(f"   Error: {type(e).__name__}: {str(e)[:100]}")
            
            print(f"\n💡 Check worker terminal - you should see:")
            print(f"      [INFO] Task worker.tasks.process_vector_task[...] received")
            print(f"      [INFO] Starting processing for VectorStatus: test-uuid-12345")
            print(f"      [ERROR] Failed to process VectorStatus ...")
        
        print(f"\n" + "=" * 60)
        print(f"  If you saw logs in worker terminal: ✅ Worker is working!")
        print(f"  If you saw NO logs: ❌ Worker is not processing tasks")
        print(f"=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error dispatching task:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
