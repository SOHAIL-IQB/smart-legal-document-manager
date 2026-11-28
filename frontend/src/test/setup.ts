// Browser APIs jsdom lacks but Radix uses (popper sizing, focus scrolling, pointer capture).
// Stand-ins only: they make the primitives mount; they don't fake any behaviour under test.
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
if (typeof Element !== 'undefined') {
  // Not in the files that run under Node (the OpenAPI drift test).
  Element.prototype.scrollIntoView ??= function scrollIntoView() {}
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.releasePointerCapture ??= () => {}
}
