import { afterEach, expect, test, vi } from 'vitest'

vi.mock('./auth', () => ({ accessToken: vi.fn().mockResolvedValue(null) }))

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

test.each(['/api', 'https://api.documind.invalid/'])('respects the explicit API base %s', async (url) => {
  vi.stubEnv('VITE_API_BASE_URL', url)
  const { default: api } = await import('./api')
  expect(api.defaults.baseURL).toBe(url.replace(/\/+$/, ''))
})
