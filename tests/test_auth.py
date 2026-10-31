from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt
import pytest

from app import auth, server


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def signed_token(key):
    def issue(**changes):
        now = datetime.now(timezone.utc)
        claims = {"sub": "alice", "iss": "https://issuer.test", "aud": "documind-api", "iat": now, "exp": now + timedelta(minutes=5), "name": "Alice"}
        claims.update(changes)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    return issue


@pytest.fixture
def authenticated_keys(monkeypatch, key):
    resolver = Mock(return_value=SimpleNamespace(get_signing_key_from_jwt=Mock(return_value=SimpleNamespace(key=key.public_key()))))
    monkeypatch.setattr(auth, "signing_keys", resolver)
    return resolver


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/files", None),
    ("get", "/files/507f1f77bcf86cd799439011", None),
    ("get", "/status/507f1f77bcf86cd799439011", None),
    ("post", "/chat", {"file_id": "id", "question": "Question?"}),
    ("post", "/analyze", {"file_id": "id"}),
    ("post", "/workflow", {"file_id": "id", "objective": "Review"}),
    ("post", "/upload", None),
    ("post", "/files/507f1f77bcf86cd799439011/retry", None),
])
def test_all_document_routes_require_sign_in(store, method, path, payload):
    with TestClient(server.app) as client:
        response = client.request(method, path, json=payload)
    assert response.status_code == 401
    store.find_one.assert_not_awaited()
    store.insert_one.assert_not_awaited()


def test_valid_access_token_has_stable_private_workspace(store, authenticated_keys, signed_token):
    with TestClient(server.app) as client:
        response = client.get("/session", headers={"Authorization": f"Bearer {signed_token()}"})
    assert response.status_code == 200
    assert response.json()["workspace_id"] == auth.Identity("https://issuer.test", "alice").workspace_id


@pytest.mark.parametrize("changes", [
    {"aud": "another-api"}, {"iss": "https://attacker.test"},
    {"exp": datetime(2000, 1, 1, tzinfo=timezone.utc)}, {"sub": ""},
])
def test_invalid_claims_are_rejected(store, authenticated_keys, signed_token, changes):
    with TestClient(server.app) as client:
        response = client.get("/session", headers={"Authorization": f"Bearer {signed_token(**changes)}"})
    assert response.status_code == 401


def test_forged_signature_rejected(store, authenticated_keys, signed_token):
    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = jwt.decode(signed_token(), options={"verify_signature": False})
    token = jwt.encode(claims, forged_key, algorithm="RS256")
    with TestClient(server.app) as client:
        assert client.get("/session", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_algorithm_confusion_rejected_before_key_lookup(store, authenticated_keys):
    token = jwt.encode({"sub": "alice"}, "a" * 64, algorithm="HS256")
    with TestClient(server.app) as client:
        assert client.get("/session", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    authenticated_keys.assert_not_called()


def test_missing_provider_configuration_fails_closed(store, monkeypatch):
    monkeypatch.delenv("OIDC_ISSUER")
    with TestClient(server.app) as client:
        assert client.get("/files").status_code == 503
    store.find.assert_not_called()


@pytest.mark.parametrize("host,environment,status", [("127.0.0.1", "development", 200), ("198.51.100.1", "development", 403), ("127.0.0.1", "production", 403)])
def test_development_identity_is_local_only(store, monkeypatch, host, environment, status):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("APP_ENV", environment)
    with TestClient(server.app, client=(host, 12345)) as client:
        assert client.get("/session", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == status
