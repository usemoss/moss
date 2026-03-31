import { describe, it, expect, vi } from 'vitest'

vi.mock('obug', () => ({ createDebug: () => () => {} }))
vi.mock('node:fs', () => ({ default: { existsSync: () => false } }))

import { mossIndexerPlugin } from '../index.js'

function setup(searchConfig: unknown) {
  const plugin = mossIndexerPlugin() as any
  plugin.configResolved({
    vitepress: {
      site: {
        themeConfig: {
          search: searchConfig,
        },
      },
    },
  })
  return plugin
}

describe('mossIndexerPlugin', () => {
  it('resolveId returns resolved id for virtual module', () => {
    const plugin = mossIndexerPlugin() as any
    const result = plugin.resolveId('virtual:moss-config')
    expect(result).toBe('\0virtual:moss-config')
  })

  it('resolveId returns undefined for unrelated ids', () => {
    const plugin = mossIndexerPlugin() as any
    const result = plugin.resolveId('some-other-module')
    expect(result).toBeUndefined()
  })

  it('load returns config JSON when provider is moss', () => {
    const plugin = setup({
      provider: 'moss',
      options: { projectId: 'p', projectKey: 'k', indexName: 'i' },
    })
    const result = plugin.load('\0virtual:moss-config')
    expect(result).toBe(
      'export default () => ({"projectId":"p","projectKey":"k","indexName":"i"})'
    )
  })

  it('load returns empty export when provider is not moss', () => {
    const plugin = setup({ provider: 'local' })
    const result = plugin.load('\0virtual:moss-config')
    expect(result).toBe('export default () => ({})')
  })
})
