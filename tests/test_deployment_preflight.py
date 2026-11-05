"""Deployment guards do not contact cloud services or use model quotas."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deployment_start', ROOT / 'deploy/production/start.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def configuration():
    return dict(APP_ENV='production', AUTH_MODE='oidc', OIDC_ISSUER='https://identity.example/',
                OIDC_AUDIENCE='https://api.example/', MONGODB_URI='mongodb+srv://example.invalid/',
                GEMINI_API_KEY='synthetic-not-a-real-key', REDIS_URL='redis://queue:6379/0',
                CORS_ORIGINS='https://frontend.example', UPLOAD_DIR='/srv/uploads',
                GEMINI_MAX_RETRIES='0', GEMINI_FALLBACK_MODELS='', LANGSMITH_TRACING='false',
                MODEL_NAME='verified-model-version', VISION_MODEL='verified-model-version',
                WORKFLOW_MODEL='verified-model-version', EMBEDDING_MODEL='gemini-embedding-001')


def test_staging_accepts_only_complete_production_configuration():
    module.validate(configuration())


@pytest.mark.parametrize('key,value', [
    ('APP_ENV', 'development'), ('AUTH_MODE', 'development'), ('OIDC_AUDIENCE', ''),
    ('OIDC_ISSUER', 'http://identity.example'), ('GEMINI_API_KEY', ''),
    ('CORS_ORIGINS', '*'), ('CORS_ORIGINS', 'http://localhost:5182'),
    ('CORS_ORIGINS', 'https://frontend.example/path'),
    ('CORS_ORIGINS', 'https://user:password@frontend.example'),
    ('UPLOAD_DIR', './uploads'), ('MODEL_NAME', 'gemini-flash-latest'),
    ('VISION_MODEL', ''), ('GEMINI_MAX_RETRIES', '2'),
    ('GEMINI_FALLBACK_MODELS', 'another-model'), ('LANGSMITH_TRACING', 'true'),
    ('MONGODB_URI', 'mongodb://example.invalid'),
    ('MONGODB_URI', 'mongodb+srv://example.invalid/?tls=false'),
    ('MONGODB_URI', 'mongodb+srv://example.invalid/?tlsAllowInvalidCertificates=true'),
])
def test_insecure_staging_configuration_fails_closed(key, value):
    env = configuration()
    env[key] = value
    with pytest.raises(ValueError):
        module.validate(env)


def test_queue_is_private_and_worker_requires_explicit_profile():
    compose = yaml.safe_load((ROOT / 'deploy/production/compose.yaml').read_text())
    assert compose['name'] == 'documind-staging'
    assert compose['services']['api']['ports'] == ['127.0.0.1:18000:8000']
    assert 'ports' not in compose['services']['queue']
    assert compose['services']['worker']['profiles'] == ['processing']
    assert compose['services']['api']['volumes'] == compose['services']['worker']['volumes']
    assert compose['services']['api']['environment']['AUTH_MODE'] == 'oidc'
    assert '--reload' not in (ROOT / 'deploy/production/start.py').read_text()


def test_showcase_cannot_collect_documents_or_connect_to_an_api():
    index = (ROOT / 'deploy/showcase/index.html').read_text()
    headers = (ROOT / 'deploy/showcase/_headers').read_text()
    assert '<form' not in index and '<script' not in index and '<input' not in index
    assert "connect-src 'none'" in index and "connect-src 'none'" in headers
    assert 'frame-ancestors \'none\'' in headers
    assert 'Static demonstration' in index
    assert 'not interactive here' in index
    assert 'synthetic' in index
