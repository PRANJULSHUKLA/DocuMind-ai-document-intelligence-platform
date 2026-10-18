import os

from dotenv import load_dotenv
from redis import Redis
from rq import Queue

load_dotenv()

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://valkey:6379/0",
)

redis_connection = Redis.from_url(
    REDIS_URL,
    socket_connect_timeout=5,
    socket_timeout=10,
    health_check_interval=30,
)

q = Queue(
    "default",
    connection=redis_connection,
    default_timeout=1200,
)