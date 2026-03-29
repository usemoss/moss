import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockFsExistsSync, mockSync } = vi.hoisted(() => {
  return {
    mockFsExistsSync: vi.fn(),
    mockSync: vi.fn()
  }
})

vi.mock('obug', () => ({ createDebug: () => () => {} }))
vi.mock('node:fs', () => ({ default: { existsSync: mockFsExistsSync } }))
vi.mock('@moss-tools/md-indexer', () => ({ sync: mockSync }))

import { mossIndexerPlugin } from '../index.js'

function setup(searchConfig: unknown) {
  const mockLogger = { error: vi.fn() }
  const plugin = mossIndexerPlugin() as any
  plugin.configResolved({
    vitepress: {
      site: {
        themeConfig: {
          search: searchConfig,
        },
      },
      root: '/test-root',
      logger: mockLogger
    },
  })
  return { plugin, mockLogger }
}
describe('mossIndexerPlugin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFsExistsSync.mockReturnValue(true)
  })

  describe('resolveId - virtual module', () => {
    it('resolves virtual:moss-config to virtual module', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('virtual:moss-config')
      expect(result).toBe('\0virtual:moss-config')
    })

    it('returns undefined for unrelated ids', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('some-other-module')
      expect(result).toBeUndefined()
    })

    it('returns undefined for empty string', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('')
      expect(result).toBeUndefined()
    })
  })

  describe('resolveId - component shadowing', () => {
    it('shadows VPNavBarSearch.vue with full path', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('/path/to/VPNavBarSearch.vue')
      expect(result).toContain('Search.vue')
    })

    it('shadows VPNavBarSearchButton.vue with full path', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('/path/to/VPNavBarSearchButton.vue')
      expect(result).toContain('SearchButton.vue')
    })

    it('shadows VPNavBarSearch.vue with relative path', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('./VPNavBarSearch.vue')
      expect(result).toContain('Search.vue')
    })

    it('shadows VPNavBarSearchButton.vue with relative path', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('./VPNavBarSearchButton.vue')
      expect(result).toContain('SearchButton.vue')
    })

    it('does not shadow when file does not exist', () => {
      mockFsExistsSync.mockReturnValue(false)
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('/path/to/VPNavBarSearch.vue')
      expect(result).toBeUndefined()
    })

    it('does not shadow other VPN components', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('/path/to/VPNavBarHome.vue')
      expect(result).toBeUndefined()
    })

    it('does not shadow VPNavBarSearch with different suffix', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.resolveId('/path/to/VPNavBarSearchExtra.vue')
      expect(result).toBeUndefined()
    })
  })

  describe('load - config loading', () => {
    it('returns config JSON when provider is moss', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'p', projectKey: 'k', indexName: 'i' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe(
        'export default () => ({"projectId":"p","projectKey":"k","indexName":"i"})'
      )
    })

    it('returns empty export when provider is not moss', () => {
      const plugin = setup({ provider: 'local' })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe('export default () => ({})')
    })

    it('returns empty export when search config is undefined', () => {
      const plugin = setup(undefined)
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe('export default () => ({})')
    })

    it('returns empty export when search config is null', () => {
      const plugin = setup(null)
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe('export default () => ({})')
    })

    it('returns empty export when search config is empty object', () => {
      const plugin = setup({})
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe('export default () => ({})')
    })

    it('returns config with empty options when options not provided', () => {
      const plugin = setup({ provider: 'moss' })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe('export default () => ({})')
    })

    it('escapes less than sign in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test<script>' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('\\u003Cscript\\u003E')
    })

    it('escapes greater than sign in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { indexName: 'test>value' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('test\\u003Evalue')
    })

    it('escapes forward slash in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectKey: 'test/path' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('test\\u002Fpath')
    })

    it('escapes backslash in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\\value' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).not.toContain('test\\value')
      expect(result).toContain('test\\\\')
    })

    it('escapes newline in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\nvalue' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).not.toMatch(/"projectId":"test\n/)
      expect(result).toContain('\\n')
    })

    it('escapes carriage return in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\rvalue' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).not.toMatch(/"projectId":"test\r/)
      expect(result).toContain('\\r')
    })

    it('escapes tab in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\tvalue' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).not.toMatch(/"projectId":"test\t/)
      expect(result).toContain('\\t')
    })

    it('escapes null character in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\u0000value' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('\\u0000')
    })

    it('escapes backspace in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\bvalue' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('\\\\b')
    })

    it('escapes form feed in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\fvalue' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).not.toMatch(/"projectId":"test\f/)
      expect(result).toContain('\\f')
    })

    it('escapes line separator in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\u2028value' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('test\\u2028value')
    })

    it('escapes paragraph separator in config values', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test\u2029value' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('test\\u2029value')
    })

    it('leaves safe characters unchanged', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test_abc_123_ABC' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('test_abc_123_ABC')
    })

    it('escapes multiple unsafe characters', () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: '<script>alert("xss")</script>' },
      })
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toContain('\\u003Cscript\\u003Ealert')
    })

    it('returns undefined for unrelated module id', () => {
      const plugin = setup({ provider: 'moss' })
      const result = plugin.load('some-other-module')
      expect(result).toBeUndefined()
    })

    it('returns empty export for resolved virtual module when no config is available', () => {
      const plugin = mossIndexerPlugin() as any
      const result = plugin.load('\0virtual:moss-config')
      expect(result).toBe('export default () => ({})')
    })
  })

  describe('buildEnd - index sync', () => {
    it('syncs index when all credentials are provided', async () => {
      mockSync.mockResolvedValue(undefined)
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test-id', projectKey: 'test-key', indexName: 'test-index' },
      })
      
      await plugin.buildEnd()
      
      expect(mockSync).toHaveBeenCalledWith({
        root: '/test-root',
        creds: {
          projectId: 'test-id',
          projectKey: 'test-key',
          indexName: 'test-index'
        }
      })
    })

    it('does not sync when provider is not moss', async () => {
      const plugin = setup({ provider: 'local' })
      
      await plugin.buildEnd()
      
      expect(mockSync).not.toHaveBeenCalled()
    })

    it('does not sync when search config is undefined', async () => {
      const plugin = setup(undefined)
      
      await plugin.buildEnd()
      
      expect(mockSync).not.toHaveBeenCalled()
    })

    it('logs error and continues when projectId is missing', async () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectKey: 'test-key', indexName: 'test-index' },
      }) as any
      
      await plugin.buildEnd()
      
      expect(mockSync).not.toHaveBeenCalled()
      expect(plugin._logger.error).toHaveBeenCalled()
      const errorCall = (plugin._logger.error as any).mock.calls[0][0]
      expect(errorCall).toContain('Missing Moss configuration')
      expect(errorCall).toContain('projectId')
    })

    it('logs error and continues when projectKey is missing', async () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test-id', indexName: 'test-index' },
      }) as any
      
      await plugin.buildEnd()
      
      expect(mockSync).not.toHaveBeenCalled()
      expect(plugin._logger.error).toHaveBeenCalled()
      const errorCall = (plugin._logger.error as any).mock.calls[0][0]
      expect(errorCall).toContain('Missing Moss configuration')
      expect(errorCall).toContain('projectKey')
    })

    it('logs error and continues when indexName is missing', async () => {
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test-id', projectKey: 'test-key' },
      }) as any
      
      await plugin.buildEnd()
      
      expect(mockSync).not.toHaveBeenCalled()
      expect(plugin._logger.error).toHaveBeenCalled()
      const errorCall = (plugin._logger.error as any).mock.calls[0][0]
      expect(errorCall).toContain('Missing Moss configuration')
      expect(errorCall).toContain('indexName')
    })

    it('logs error and continues when all credentials are missing', async () => {
      const plugin = setup({
        provider: 'moss',
        options: {},
      }) as any
      
      await plugin.buildEnd()
      
      expect(mockSync).not.toHaveBeenCalled()
      expect(plugin._logger.error).toHaveBeenCalled()
    })

    it('logs error and continues when sync fails', async () => {
      mockSync.mockRejectedValue(new Error('Network error'))
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test-id', projectKey: 'test-key', indexName: 'test-index' },
      }) as any
      
      await plugin.buildEnd()
      
      expect(mockSync).toHaveBeenCalled()
      expect(plugin._logger.error).toHaveBeenCalled()
      const errorCall = (plugin._logger.error as any).mock.calls[0][0]
      expect(errorCall).toContain('Moss index sync failed')
      expect(errorCall).toContain('Network error')
    })

    it('allows build to continue after sync failure', async () => {
      mockSync.mockRejectedValue(new Error('Test error'))
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test-id', projectKey: 'test-key', indexName: 'test-index' },
      }) as any
      
      await expect(plugin.buildEnd()).resolves.not.toThrow()
    })
  })

  describe('closeBundle', () => {
    it('delegates to buildEnd', async () => {
      mockSync.mockResolvedValue(undefined)
      const plugin = setup({
        provider: 'moss',
        options: { projectId: 'test-id', projectKey: 'test-key', indexName: 'test-index' },
      })
      
      await plugin.closeBundle()
      
      expect(mockSync).toHaveBeenCalled()
    })

    it('handles buildEnd not being a function gracefully', async () => {
      const plugin = mossIndexerPlugin() as any
      plugin.buildEnd = undefined
      
      await expect(plugin.closeBundle()).resolves.not.toThrow()
    })
  })

  describe('plugin metadata', () => {
    it('has correct name', () => {
      const plugin = mossIndexerPlugin() as any
      expect(plugin.name).toBe('vitepress:moss-indexer')
    })

    it('enforces pre order', () => {
      const plugin = mossIndexerPlugin() as any
      expect(plugin.enforce).toBe('pre')
    })
  })
})
