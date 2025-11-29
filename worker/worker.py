"""
RQ Worker entry point
"""
import os
import sys
import redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv
import logging
from pathlib import Path

load_dotenv()

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Add backend to Python path so we can import models
# This handles both local development and Render deployment
worker_dir = Path(__file__).resolve().parent
backend_dir = worker_dir.parent / "backend"
if backend_dir.exists():
    sys.path.insert(0, str(backend_dir))
    logger.info(f"Added backend to path: {backend_dir}")
else:
    # If backend is not in parent, try current directory structure
    # Render might have different structure
    logger.warning(f"Backend directory not found at {backend_dir}, using current path")

# Redis connection
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_conn = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
    redis_conn.ping()
    logger.info(f"✅ Connected to Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
except Exception as e:
    logger.error(f"❌ Failed to connect to Redis: {e}")
    logger.error(f"Redis URL: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
    raise

# Queue names
discovery_queue = Queue("discovery", connection=redis_conn)
enrichment_queue = Queue("enrichment", connection=redis_conn)
scoring_queue = Queue("scoring", connection=redis_conn)
send_queue = Queue("send", connection=redis_conn)
followup_queue = Queue("followup", connection=redis_conn)

if __name__ == "__main__":
    logger.info("Starting RQ worker...")
    logger.info(f"Redis URL: {redis_url}")
    logger.info("Listening to queues: discovery, enrichment, scoring, send, followup")
    
    with Connection(redis_conn):
        worker = Worker([discovery_queue, enrichment_queue, scoring_queue, send_queue, followup_queue])
        worker.work()

