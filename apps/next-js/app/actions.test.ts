import { describe, it, expect } from 'vitest'
import type { DocInput } from './actions'

describe('DocInput type', () => {
  it('accepts a valid document', () => {
    const doc: DocInput = { id: '1', text: 'hello' }
    expect(doc.id).toBe('1')
    expect(doc.text).toBe('hello')
  })

  it('accepts optional metadata', () => {
    const doc: DocInput = { id: '2', text: 'world', metadata: { source: 'test' } }
    expect(doc.metadata?.source).toBe('test')
  })
})
