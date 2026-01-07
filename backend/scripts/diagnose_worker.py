"""
Complete Worker Diagnostics - Check Everything
===============================================
"""

import sys
import redis
from config.settings import get_settings

def check_redis_queues():
    """Check if tasks are actually in Redis queues."""
    print("\n" + "=" * 60)
    print("  REDIS QUEUE STATUS")
    print("=" * 60)
    
    settings = get_settings()
    
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True
        )
        
        # Check both queues
        for queue_name in ['queue_heavy', 'queue_fast']:
            length = r.llen(queue_name)
            print(f"\n📊 Queue: {queue_name}")
            print(f"   Messages waiting: {length}")
            
            if length > 0:
                # Peek at first message
                first_msg = r.lindex(queue_name, 0)
                print(f"   First message preview: {first_msg[:100] if first_msg else 'None'}...")
        
        # Check celery queue (default name)
        celery_length = r.llen('celery')
        if celery_length > 0:
            print(f"\n📊 Queue: celery (default)")
            print(f"   Messages waiting: {celery_length}")
        
        return True
    except Exception as e:
        print(f"\n❌ Redis error: {e}")
        return False


def check_database_status():
    """Check VectorStatus in database."""
    print("\n" + "=" * 60)
    print("  DATABASE STATUS")
    print("=" * 60)
    
    try:
        from shared.database import get_session
        from app.models.vector_status import VectorStatus
        from sqlmodel import select, func
        
        session = next(get_session())
        
        # Count by status
        statement = select(
            VectorStatus.status,
            func.count(VectorStatus.id).label('count')
        ).group_by(VectorStatus.status)
        
        results = session.exec(statement).all()
        
        print("\n📊 VectorStatus counts:")
        for status, count in results:
            print(f"   {status}: {count}")
        
        # Get some PENDING tasks
        pending_statement = select(VectorStatus).where(
            VectorStatus.status == "pending"
        ).limit(3)
        
        pending_tasks = session.exec(pending_statement).all()
        
        if pending_tasks:
            print(f"\n📋 Sample PENDING tasks:")
            for vs in pending_tasks:
                print(f"   UUID: {vs.id}")
                print(f"   VectorType: {vs.vector_type}")
                print(f"   Asset ID: {vs.asset_id}")
                print()
        
        session.close()
        return True
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_worker_import():
    """Check if worker module can be imported."""
    print("\n" + "=" * 60)
    print("  WORKER MODULE IMPORT")
    print("=" * 60)
    
    try:
        print("\n🔍 Importing app.core.celery_app...")
        from app.core.celery_app import app
        print(f"✅ Celery app: {app.main}")
        
        print("\n🔍 Importing worker.tasks...")
        import worker.tasks
        print(f"✅ worker.tasks module loaded")
        
        print("\n🔍 Checking process_vector_task...")
        if hasattr(worker.tasks, 'process_vector_task'):
            print(f"✅ process_vector_task function exists")
            
            # Check if it's registered with Celery
            task_name = 'worker.tasks.process_vector_task'
            if task_name in app.tasks:
                print(f"✅ Task registered in Celery: {task_name}")
            else:
                print(f"❌ Task NOT registered in Celery!")
                print(f"   Registered tasks: {[t for t in app.tasks.keys() if 'worker' in t]}")
                return False
        else:
            print(f"❌ process_vector_task not found in worker.tasks")
            return False
        
        return True
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def manual_task_dispatch():
    """Try to manually dispatch a task."""
    print("\n" + "=" * 60)
    print("  MANUAL TASK DISPATCH TEST")
    print("=" * 60)
    
    try:
        from app.core.celery_app import app
        from shared.database import get_session
        from app.models.vector_status import VectorStatus
        from sqlmodel import select
        
        # Get a real PENDING task
        session = next(get_session())
        statement = select(VectorStatus).where(
            VectorStatus.status == "pending"
        ).limit(1)
        
        vs = session.exec(statement).first()
        
        if not vs:
            print("\n⚠️  No PENDING tasks found")
            print("   Run dispatch from frontend first")
            return True
        
        print(f"\n📤 Dispatching task manually:")
        print(f"   VectorStatus ID: {vs.id}")
        print(f"   VectorType: {vs.vector_type}")
        
        result = app.send_task(
            'worker.tasks.process_vector_task',
            args=[str(vs.id)],
            queue='queue_fast'
        )
        
        print(f"\n✅ Task sent!")
        print(f"   Celery Task ID: {result.id}")
        print(f"   State: {result.state}")
        
        print(f"\n⏳ Waiting 5 seconds for result...")
        try:
            output = result.get(timeout=5)
            print(f"✅ Task completed: {output}")
        except Exception as e:
            print(f"⚠️  Timeout or error: {type(e).__name__}")
            print(f"   This is normal if worker is not running")
        
        session.close()
        return True
    except Exception as e:
        print(f"\n❌ Dispatch error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "FULL DIAGNOSTICS" + " " * 27 + "║")
    print("╚" + "=" * 58 + "╝")
    
    tests = [
        ("Worker Module Import", check_worker_import),
        ("Redis Queue Status", check_redis_queues),
        ("Database Status", check_database_status),
        ("Manual Task Dispatch", manual_task_dispatch),
    ]
    
    results = []
    for name, func in tests:
        try:
            result = func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n✅ Diagnostics passed!")
        print("\n💡 If worker still not processing:")
        print("   1. Check worker terminal is actually RUNNING")
        print("   2. Verify worker shows 'celery@hostname ready'")
        print("   3. Look for errors in worker startup")
    else:
        print("\n⚠️  Issues found - see errors above")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
