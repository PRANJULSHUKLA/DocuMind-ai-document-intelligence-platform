"""Fail closed for private staging. This does not certify public release readiness."""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def validate(environment):
    if environment.get('APP_ENV') != 'production' or environment.get('AUTH_MODE') != 'oidc':
        raise ValueError('Staging requires production mode and managed OIDC.')
    for key in ('OIDC_AUDIENCE', 'MONGODB_URI', 'GEMINI_API_KEY', 'REDIS_URL'):
        if not environment.get(key, '').strip():
            raise ValueError(f'{key} is required.')
    database = urlsplit(environment['MONGODB_URI'])
    unsafe = {'tlsinsecure', 'tlsallowinvalidcertificates', 'tlsallowinvalidhostnames'}
    parameters = {key.lower(): values for key, values in parse_qs(database.query).items()}
    if database.scheme != 'mongodb+srv' or any(
        value.lower() in ('true', '1') for key in unsafe for value in parameters.get(key, [])
    ) or any(value.lower() in ('false', '0') for value in parameters.get('tls', [])):
        raise ValueError('Atlas requires SRV and normal certificate-validated TLS.')
    issuer = urlsplit(environment.get('OIDC_ISSUER', ''))
    if issuer.scheme != 'https' or not issuer.hostname or issuer.username or issuer.password:
        raise ValueError('OIDC issuer must use HTTPS.')
    origins = [value.strip() for value in environment.get('CORS_ORIGINS', '').split(',') if value.strip()]
    if not origins:
        raise ValueError('An exact HTTPS frontend origin is required.')
    for value in origins:
        origin = urlsplit(value)
        if (origin.scheme != 'https' or not origin.hostname or '*' in value
                or origin.username or origin.password or origin.query or origin.fragment
                or origin.path not in ('', '/') or origin.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('CORS must list exact HTTPS frontend origins.')
    if not Path(environment.get('UPLOAD_DIR', '')).is_absolute():
        raise ValueError('UPLOAD_DIR must be an absolute private path.')
    if environment.get('GEMINI_MAX_RETRIES') != '0' or environment.get('GEMINI_FALLBACK_MODELS', '').strip():
        raise ValueError('Zero-cost staging disables automatic model retries and fallbacks by configuration.')
    for key in ('MODEL_NAME', 'VISION_MODEL', 'WORKFLOW_MODEL', 'EMBEDDING_MODEL'):
        model = environment.get(key, '').strip()
        if not model or 'latest' in model:
            raise ValueError(f'{key} must name a model verified in this project free quota.')
    if environment.get('LANGSMITH_TRACING', '').lower() != 'false':
        raise ValueError('External tracing must be disabled in this staging configuration.')


def main():
    import sys
    try:
        validate(os.environ)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    if mode == 'api':
        command = ['python', '-m', 'uvicorn', 'app.server:app', '--host', '0.0.0.0', '--port', '8000',
                   '--workers', '1', '--limit-concurrency', '8', '--backlog', '16', '--timeout-keep-alive', '5',
                   '--timeout-graceful-shutdown', '30', '--no-proxy-headers']
    elif mode == 'worker':
        command = ['python', '-m', 'app.queue.worker_main']
    else:
        raise SystemExit('Choose api or worker.')
    os.execvp(command[0], command)


if __name__ == '__main__':
    main()
