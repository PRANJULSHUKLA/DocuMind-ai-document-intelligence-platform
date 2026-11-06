"""Supervise one API, one RQ worker and a loopback-only ephemeral queue."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def validate(environment):
    # Reuse all production-mode/TLS/model checks; no development auth fallback.
    from deploy.production.start import validate as production_validate
    production_validate(environment)
    if environment.get('DOCUMIND_RENDER_PILOT') != '1':
        raise ValueError('Explicit Render pilot opt-in is required.')
    if not environment.get('PILOT_ALLOWED_SUBJECTS', '').strip():
        raise ValueError('At least one approved Auth0 subject is required.')
    if environment.get('REDIS_URL') != 'redis://127.0.0.1:6379/0':
        raise ValueError('The pilot queue must be local and private.')
    if environment.get('MAX_UPLOAD_MB') != '2':
        raise ValueError('Pilot uploads must be limited to 2 MB.')
    if not environment.get('DATABASE_NAME', '').strip():
        raise ValueError('The reviewed database name is required.')
    port = int(environment.get('PORT', '10000'))
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid Render HTTP port.')


def main():
    validate(os.environ)
    Path(os.environ['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    children = []

    def shutdown(*_):
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 15
        for child in reversed(children):
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

    def stop(*_):
        shutdown()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--protected-mode', 'yes',
                                         '--save', '', '--appendonly', 'no', '--maxmemory', '24mb',
                                         '--maxmemory-policy', 'noeviction']))
        from redis import Redis
        connection = Redis.from_url(os.environ['REDIS_URL'], socket_connect_timeout=1, socket_timeout=1)
        for _ in range(50):
            if children[0].poll() is not None:
                raise RuntimeError('Private queue exited.')
            try:
                if connection.ping():
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError('Private queue did not become ready.')
        connection.close()
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.pilot_server:app',
                                         '--host', '0.0.0.0', '--port', os.environ.get('PORT', '10000'),
                                         '--workers', '1', '--limit-concurrency', '4', '--backlog', '8',
                                         '--no-proxy-headers']))
        children.append(subprocess.Popen([sys.executable, '-m', 'app.queue.worker_main']))
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise RuntimeError('A pilot child process exited; stopping the complete service.')
    finally:
        shutdown()


if __name__ == '__main__':
    # Add repository root when invoked as python deploy/render/start.py.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
