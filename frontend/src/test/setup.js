import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.stubGlobal('fetch', () => { throw new Error('Unexpected external request in offline UI test') })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
