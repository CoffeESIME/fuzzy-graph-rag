"""
Celery Configuration Test Script
=================================

This script verifies the Celery setup:
1. Redis broker connectivity
2. Redis result backend connectivity
3. Queue configuration
4. Task autodiscovery
"""

import sys
from app.core.celery_app import app, QUEUE_HEAVY, QUEUE_FAST
from config.settings import get_settings
import redis

def check_redis_connection():
    """Test Redis broker and backend connections."""
    settings = get_settings()
    
    print("🔍 Testing Redis Connections...\n")
    
    # Test broker (db=0)
    try:
        broker_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True
        )
        broker_client.ping()
        print(f"✅ Broker (redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0) - Connected")
    except Exception as e:
        print(f"❌ Broker connection failed: {e}")
        return False
    
    # Test result backend (db=1)
    try:
        backend_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=1,
            decode_responses=True
        )
        backend_client.ping()
        print(f"✅ Backend (redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1) - Connected")
    except Exception as e:
        print(f"❌ Backend connection failed: {e}")
        return False
    
    return True


def check_celery_config():
    """Verify Celery app configuration."""
    print("\n🔍 Checking Celery Configuration...\n")
    
    print(f"App Name: {app.main}")
    print(f"Broker: {app.conf.broker_url}")
    print(f"Backend: {app.conf.result_backend}")
    print(f"Task Serializer: {app.conf.task_serializer}")
    print(f"Acks Late: {app.conf.task_acks_late}")
    print(f"Prefetch Multiplier: {app.conf.worker_prefetch_multiplier}")
    
    print(f"\n📋 Configured Queues:")
    print(f"  - {QUEUE_HEAVY} (GPU-intensive)")
    print(f"  - {QUEUE_FAST} (CPU-light)")
    
    print(f"\n📦 Task Routes:")
    for task_name, route_config in app.conf.task_routes.items():
        queue = route_config.get('queue', 'default')
        print(f"  - {task_name} → {queue}")
    
    return True


def check_task_discovery():
    """Verify task autodiscovery."""
    print("\n🔍 Checking Task Discovery...\n")
    
    try:
        # Get registered tasks
        task_names = list(app.tasks.keys())
        
        # Filter out Celery internal tasks
        custom_tasks = [t for t in task_names if not t.startswith('celery.')]
        
        if custom_tasks:
            print(f"✅ Found {len(custom_tasks)} custom task(s):")
            for task in custom_tasks:
                print(f"  - {task}")
        else:
            print("⚠️  No custom tasks found yet (this is OK if worker.tasks.py is not implemented)")
        
        return True
    except Exception as e:
        print(f"❌ Task discovery failed: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("  CELERY CONFIGURATION TEST")
    print("=" * 60)
    
    checks = [
        ("Redis Connections", check_redis_connection),
        ("Celery Config", check_celery_config),
        ("Task Discovery", check_task_discovery),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 All checks passed! Celery is ready to use.")
        print("\nNext steps:")
        print("  1. Start a worker: poetry run celery -A app.core.celery_app worker --loglevel=info --queues=queue_heavy,queue_fast")
        print("  2. Implement tasks in worker/tasks.py")
        print("  3. Update dispatcher endpoint to use: from app.core.celery_app import app")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
