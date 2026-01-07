"""
Quick Redis Queue Check
========================
Check if tasks are actually in Redis queues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from config.settings import get_settings

settings = get_settings()

print("=" * 60)
print("REDIS QUEUE CHECK")
print("=" * 60)

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,  # Broker db
    decode_responses=True
)

print(f"\nConnected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}/0")
print(f"\nQueue lengths:")

for queue in ['queue_heavy', 'queue_fast', 'celery']:
    length = r.llen(queue)
    print(f"  {queue}: {length} message(s)")
    
    if length > 0:
        # Show first message
        msg = r.lindex(queue, 0)
        print(f"    First message preview: {msg[:200] if msg else 'None'}...")

# List all keys
print(f"\nAll keys in Redis db=0:")
keys = r.keys('*')
for key in keys[:20]:
    key_type = r.type(key)
    print(f"  {key} ({key_type})")

if len(keys) > 20:
    print(f"  ... and {len(keys) - 20} more keys")

print("\n" + "=" * 60)
