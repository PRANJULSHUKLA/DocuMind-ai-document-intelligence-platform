"""Start RQ using the same configured queue connection as the API."""
from rq import Worker

from app.queue.q import q, redis_connection


if __name__ == "__main__":
    Worker([q], connection=redis_connection).work()
