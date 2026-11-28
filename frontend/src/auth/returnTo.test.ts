import { expect, test } from 'vitest'

import { returnPath } from './returnTo'

test('returns to the guarded page the visitor came from', () => {
  expect(returnPath({ from: '/documents/12?tab=history' })).toBe('/documents/12?tab=history')
})

test('anything that is not one of our own pages goes to the documents instead', () => {
  for (const state of [
    null,
    undefined,
    {},
    { from: 42 },
    { from: 'https://evil.example/' },
    { from: '//evil.example/path' }, // protocol-relative: leaves the site
    { from: 'documents' },
    { from: '/sign-in' },
    { from: '/sign-up?x=1' },
  ]) {
    expect(returnPath(state)).toBe('/documents')
  }
})
