import { UserManager, WebStorageStateStore } from 'oidc-client-ts'

export const developmentIdentity = import.meta.env.DEV && import.meta.env.VITE_AUTH_MODE === 'development'
export const signInConfigured = Boolean(import.meta.env.VITE_OIDC_AUTHORITY && import.meta.env.VITE_OIDC_CLIENT_ID)
let manager
let initialization

function getManager() {
  if (!signInConfigured) throw new Error('Sign-in is not configured.')
  manager ??= new UserManager({
    authority: import.meta.env.VITE_OIDC_AUTHORITY,
    client_id: import.meta.env.VITE_OIDC_CLIENT_ID,
    redirect_uri: `${window.location.origin}/auth/callback`,
    post_logout_redirect_uri: window.location.origin,
    response_type: 'code',
    scope: import.meta.env.VITE_OIDC_SCOPE || 'openid profile email',
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: true,
    extraQueryParams: import.meta.env.VITE_OIDC_AUDIENCE
      ? { audience: import.meta.env.VITE_OIDC_AUDIENCE }
      : {},
  })
  return manager
}

export function initializeAuth() {
  // React StrictMode may mount twice; a callback must only be consumed once.
  initialization ??= (async () => {
    const client = getManager()
    if (window.location.pathname === '/auth/callback') {
      const user = await client.signinRedirectCallback()
      window.history.replaceState({}, '', '/')
      return user
    }
    const user = await client.getUser()
    return user && !user.expired ? user : null
  })().catch(() => {
    initialization = undefined
    throw new Error('Unable to complete sign-in. Please try again.')
  })
  return initialization
}

export const signIn = () => getManager().signinRedirect()

export async function clearSession() {
  if (manager) await manager.removeUser()
  initialization = undefined
}

export async function signOut() {
  const client = getManager()
  const metadata = await client.metadataService.getMetadata()
  if (metadata.end_session_endpoint) {
    await client.signoutRedirect()
  } else {
    await clearSession()
    window.location.assign('/')
  }
}

export async function accessToken() {
  if (developmentIdentity || !signInConfigured) return null
  const user = await getManager().getUser()
  if (!user || user.expired) {
    window.dispatchEvent(new Event('documind:session-expired'))
    throw new Error('Your session has expired. Please sign in again.')
  }
  return user.access_token
}
