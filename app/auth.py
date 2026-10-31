"""Provider-neutral OIDC access-token verification and private workspace identity."""
import asyncio
import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str
    name: str = ""

    @property
    def workspace_id(self) -> str:
        digest = hashlib.sha256(f"{self.issuer}\0{self.subject}".encode()).hexdigest()
        return f"personal_{digest}"


@lru_cache(maxsize=8)
def signing_keys(issuer: str, explicit_jwks: str):
    if explicit_jwks:
        url = explicit_jwks
    else:
        response = httpx.get(
            issuer.rstrip("/") + "/.well-known/openid-configuration",
            timeout=10, follow_redirects=False,
        )
        response.raise_for_status()
        metadata = response.json()
        if metadata.get("issuer") != issuer:
            raise ValueError("OIDC discovery issuer mismatch")
        url = metadata["jwks_uri"]
    if urlparse(url).scheme != "https":
        raise ValueError("OIDC signing keys require HTTPS")
    return jwt.PyJWKClient(url, timeout=10, cache_jwk_set=True, lifespan=300)


def verify_token(token: str, issuer: str, audience: str) -> Identity:
    if len(token) > 16384 or jwt.get_unverified_header(token).get("alg") != "RS256":
        raise jwt.InvalidTokenError("Unsupported access token")
    key = signing_keys(issuer, os.getenv("OIDC_JWKS_URL", "")).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token, key.key, algorithms=["RS256"], audience=audience, issuer=issuer,
        leeway=30, options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )
    if not isinstance(claims["sub"], str) or not claims["sub"].strip():
        raise jwt.InvalidTokenError("Missing subject")
    return Identity(issuer=issuer, subject=claims["sub"], name=str(claims.get("name", "")))


async def current_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Identity:
    mode = os.getenv("AUTH_MODE", "oidc").strip().lower()
    if mode == "development":
        # Explicit opt-in; forwarding headers never grant this exception.
        if os.getenv("APP_ENV", "development").strip().lower() == "production" or not request.client or request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(403, "Development identity is restricted to local requests.")
        return Identity("urn:documind:development", "local-developer", "Local developer")
    if mode != "oidc":
        raise HTTPException(503, "Invalid authentication configuration.")
    issuer, audience = os.getenv("OIDC_ISSUER", ""), os.getenv("OIDC_AUDIENCE", "")
    if not issuer or not audience or urlparse(issuer).scheme != "https":
        raise HTTPException(503, "Managed sign-in is not configured.")
    if credentials is None:
        raise HTTPException(401, "Sign-in required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        return await asyncio.to_thread(verify_token, credentials.credentials, issuer, audience)
    except (jwt.PyJWKClientConnectionError, httpx.HTTPError):
        raise HTTPException(503, "Sign-in provider is temporarily unavailable.") from None
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Invalid or expired access token.", headers={"WWW-Authenticate": "Bearer"}) from None
