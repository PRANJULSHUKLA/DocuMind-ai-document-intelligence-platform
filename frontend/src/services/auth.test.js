import { afterEach, beforeEach, expect, test, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  settings: null,
  getUser: vi.fn(),
  callback: vi.fn(),
}))

vi.mock('oidc-client-ts', () => ({
  UserManager: class {
    constructor(settings) { mocks.settings = settings }
    getUser = mocks.getUser
    signinRedirectCallback = mocks.callback
  },
  WebStorageStateStore: class {},
}))

beforeEach(() => {
  vi.resetModules()
  mocks.getUser.mockReset()
  mocks.callback.mockReset()
  vi.stubEnv('VITE_AUTH_MODE', 'oidc')
  vi.stubEnv('VITE_OIDC_AUTHORITY', 'https://issuer.test')
  vi.stubEnv('VITE_OIDC_CLIENT_ID', 'frontend-client')
  window.history.replaceState({}, '', '/')
})

afterEach(() => vi.unstubAllEnvs())

test('API requests receive the access token rather than the ID token', async () => {
  mocks.getUser.mockResolvedValue({ access_token: 'test-access-token', id_token: 'test-id-token', expired: false })
  const auth = await import('./auth')
  expect(await auth.accessToken()).toBe('test-access-token')
  expect(mocks.settings.response_type).toBe('code')
  expect(mocks.settings.client_secret).toBeUndefined()
})

test('expired sessions cannot supply an API token', async () => {
  mocks.getUser.mockResolvedValue({ access_token: 'expired', expired: true })
  const auth = await import('./auth')
  await expect(auth.accessToken()).rejects.toThrow('expired')
})

test('StrictMode initialization consumes the callback once', async () => {
  window.history.replaceState({}, '', '/auth/callback?code=test-code&state=test-state')
  mocks.callback.mockResolvedValue({ profile: { name: 'Alice' }, expired: false })
  const auth = await import('./auth')
  await Promise.all([auth.initializeAuth(), auth.initializeAuth()])
  expect(mocks.callback).toHaveBeenCalledTimes(1)
  expect(window.location.pathname).toBe('/')
  expect(window.location.search).toBe('')
})
