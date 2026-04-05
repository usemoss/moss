import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockLoadIndex = vi.fn()
const mockQuery = vi.fn()

vi.mock('@inferedge/moss', () => ({
  MossClient: vi.fn().mockImplementation(() => ({
    loadIndex: mockLoadIndex,
    query: mockQuery,
  })),
}))

describe('searchMoss', () => {
  const originalEnv = { ...process.env }

  beforeEach(() => {
    vi.resetModules()
    mockLoadIndex.mockReset()
    mockQuery.mockReset()
    process.env.MOSS_PROJECT_ID = 'pid'
    process.env.MOSS_PROJECT_KEY = 'pkey'
    process.env.MOSS_INDEX_NAME = 'idx'
  })

  afterEach(() => {
    process.env = { ...originalEnv }
  })

  it('returns success with docs and timeTaken', async () => {
    mockLoadIndex.mockResolvedValue(undefined)
    mockQuery.mockResolvedValue({
      docs: [
        { id: '1', text: 'hello', score: 0.9, metadata: { title: 'Hello' } },
      ],
      timeTakenInMs: 42,
    })

    const { searchMoss } = await import('./actions')
    const result = await searchMoss('test')

    expect(result).toEqual({
      success: true,
      docs: [{ id: '1', text: 'hello', score: 0.9, metadata: { title: 'Hello' } }],
      timeTaken: 42,
    })
  })

  it('throws when env vars are missing', async () => {
    delete process.env.MOSS_PROJECT_ID
    delete process.env.MOSS_PROJECT_KEY
    delete process.env.MOSS_INDEX_NAME

    const { searchMoss } = await import('./actions')

    await expect(searchMoss('q')).rejects.toThrow(
      'Missing Moss credentials in environment variables.'
    )
  })

  it('returns error on API failure', async () => {
    mockLoadIndex.mockRejectedValue(new Error('network down'))
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const { searchMoss } = await import('./actions')
    const result = await searchMoss('q')

    expect(result).toEqual({ success: false, error: 'network down' })
    errorSpy.mockRestore()
  })
})
