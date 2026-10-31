// @vitest-environment node
import { expect, test } from 'vitest'
import config from './vite.config'

test('the loopback development proxy rewrites API paths without enabling a preview gateway', () => {
  expect(config.server.host).toBe('127.0.0.1')
  expect(config.server.proxy['/api'].target).toBe('http://127.0.0.1:8000')
  expect(config.server.proxy['/api'].rewrite('/api/files')).toBe('/files')
  expect(config.preview.proxy).toEqual({})
  expect(config.preview.host).toBe('127.0.0.1')
})
