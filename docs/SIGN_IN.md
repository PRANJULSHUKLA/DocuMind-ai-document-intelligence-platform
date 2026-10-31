# Managed Google / Microsoft sign-in

DocuMind uses Authorization Code flow with PKCE in the browser and independently
verifies API access tokens on the server. Choose a managed OIDC provider that
supports your desired Google/Microsoft connections and issues **RS256 JWT access
tokens for your API**. Google/Microsoft social sign-in is configured at that
provider; DocuMind does not store passwords or a browser client secret.

## Provider application

1. Register a public Single Page Application (SPA).
2. Enable Authorization Code flow with PKCE. Do not configure a frontend secret.
3. Register an API/resource audience for DocuMind, with RS256 signing.
4. Enable the Google and/or Microsoft identity connections you need.
5. Allow callback `http://localhost:5173/auth/callback`, logout return
   `http://localhost:5173`, and web origin `http://localhost:5173` for development.
6. Add the equivalent exact HTTPS URLs for your deployed frontend.
7. Configure API scopes/consent for the provider and include the required API
   scope in the frontend scope setting. A provider's ordinary ID token or opaque
   access token is not a substitute for a JWT access token addressed to this API.

Use the exact issuer value from discovery, including a trailing slash if present.
Provider-specific scope and audience syntax vary. For example, providers that
take an `audience` authorization parameter use `VITE_OIDC_AUDIENCE`; providers
that select resources through scopes use `VITE_OIDC_SCOPE` instead.

## Application settings

Backend `.env`:

```dotenv
APP_ENV=production
AUTH_MODE=oidc
OIDC_ISSUER=https://your-identity-provider.example/
OIDC_AUDIENCE=your-documind-api-audience
CORS_ORIGINS=https://your-documind-frontend.example
```

Frontend build environment:

```dotenv
VITE_AUTH_MODE=oidc
VITE_API_BASE_URL=https://your-documind-api.example
VITE_OIDC_AUTHORITY=https://your-identity-provider.example/
VITE_OIDC_CLIENT_ID=your-public-spa-client-id
VITE_OIDC_SCOPE=openid profile email your-required-api-scope
VITE_OIDC_AUDIENCE=
```

Set `VITE_OIDC_AUDIENCE` if required by the provider. `OIDC_JWKS_URL` is an optional
backend override; otherwise the backend reads the trusted issuer's discovery
document. HTTPS is required for discovery/signing keys. Configure static hosting
to serve `index.html` at `/auth/callback`. Restart/rebuild after environment changes.

The server checks signature, fixed RS256 algorithm, issuer, audience, expiry,
issued-at, and subject. Missing configuration fails closed. Sessions use access
tokens for API calls, and expired sessions return to sign-in. Browser state and
tokens use session storage; deploy with HTTPS and appropriate XSS protections.

## Existing documents

Documents predating ownership support remain hidden. During maintenance, stop
uploads and workers and back up the database. Obtain the intended owner's exact
verified issuer and subject from the identity provider. Review the dry-run:

```sh
python scripts/assign_legacy_workspace.py --issuer 'https://your-identity-provider.example/' --subject 'verified-owner-subject'
```

This reports counts and the target workspace without modifying data. The tool
handles all unassigned documents as a single-owner legacy collection; do not use
it if different documents belong to different people. Confirm ownership first.
Only after reviewing the target, rerun with `--apply`. Existing assigned documents
are never transferred; interrupted chunk assignment can be resumed for the same
owner. The tool does not change PDF files, content, embeddings, or the index.

Local development has its own identity. Its documents also require an intentional
ownership migration before a managed account may access them; the legacy tool
does not transfer already assigned workspaces.

## Acceptance check

- Signed-out requests to every document endpoint return 401.
- One account cannot list or access another account's documents.
- A successful sign-in reaches `/session` and supplies an API access token.
- Incorrect audience/issuer, expired tokens, and forged signatures are rejected.
- Provider outage returns an actionable failure without bypassing verification.
- Production rejects development identity mode.
- Logout clears the local session and uses provider logout when supported.

Implementation references: [oidc-client-ts UserManager](https://authts.github.io/oidc-client-ts/classes/UserManager.html),
[PyJWT verification](https://pyjwt.readthedocs.io/en/stable/usage.html).
