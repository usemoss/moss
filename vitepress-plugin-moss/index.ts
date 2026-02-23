import { createDebug } from 'obug'
import type { Plugin } from 'vite'
import type { SiteConfig, DefaultTheme } from 'vitepress'
import { sync } from '@moss-tools/md-indexer'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'

export type { MossSearchOptions } from './types.js'

const debug = createDebug('vitepress:moss-indexer')
const __dirname = path.dirname(fileURLToPath(import.meta.url))

export function mossIndexerPlugin(): Plugin {
  const virtualModuleId = 'virtual:moss-config'
  const resolvedVirtualModuleId = '\0' + virtualModuleId
  let siteConfig: SiteConfig<DefaultTheme.Config>

  return {
    name: 'vitepress:moss-indexer',
    enforce: 'pre',
    resolveId(id) {
      if (id === virtualModuleId) {
        return resolvedVirtualModuleId
      }
      
      // Shadowing components
      if (id.endsWith('/VPNavBarSearch.vue') || id === './VPNavBarSearch.vue') {
        const replacement = path.resolve(__dirname, '..', 'Search.vue')
        if (fs.existsSync(replacement)) {
          console.error(`[MossPlugin] Shadowing VPNavBarSearch.vue -> ${replacement}`)
          return replacement
        }
      }
      if (id.endsWith('/VPNavBarSearchButton.vue') || id === './VPNavBarSearchButton.vue') {
        const replacement = path.resolve(__dirname, '..', 'SearchButton.vue')
        if (fs.existsSync(replacement)) {
          console.error(`[MossPlugin] Shadowing VPNavBarSearchButton.vue -> ${replacement}`)
          return replacement
        }
      }
    },
    configResolved(config) {
      console.error('[MossPlugin] configResolved called')
      siteConfig = (config as any).vitepress
    },
    load(id) {
      if (id === resolvedVirtualModuleId) {
        // If siteConfig isn't available yet or search isn't moss, return empty config
        if (siteConfig?.site?.themeConfig?.search?.provider !== 'moss') {
          return 'export default () => ({})'
        }
        const searchOptions = siteConfig.site.themeConfig.search.options || {}
        return `export default () => (${JSON.stringify(searchOptions)})`
      }
    },
    async buildEnd() {
      // Only run when siteConfig is available and Moss search is enabled
      if (!siteConfig || siteConfig.site.themeConfig?.search?.provider !== 'moss') {
        return
      }

      // Only run for client build and only during production build
      // NOTE: environment.name is used in newer Vite/VitePress
      const environment = (this as any).environment
      if (
        (environment && environment.name !== 'client') ||
        process.env.NODE_ENV !== 'production'
      )
        return

      try {
        debug('Starting Moss index sync...')

        const searchConfig = siteConfig.site.themeConfig?.search
        const searchOptions =
          searchConfig?.provider === 'moss' ? searchConfig.options : undefined

        // Get credentials from config options only
        const projectId = searchOptions?.projectId
        const projectKey = searchOptions?.projectKey
        const indexName = searchOptions?.indexName

        // Validate required credentials
        if (!projectId || !projectKey || !indexName) {
          throw new Error(
            'Missing Moss configuration: projectId, projectKey, and indexName must be provided in themeConfig.search.options. ' +
              'Example: search: { provider: "moss", options: { projectId: "...", projectKey: "...", indexName: "..." } }'
          )
        }

        const creds = {
          projectId,
          projectKey,
          indexName
        }

        await sync({
          root: siteConfig.srcDir,
          creds
        })

        debug('✅ Moss index sync completed.')
      } catch (error) {
        const err = error as Error
        siteConfig.logger.error(
          `Moss index sync failed: ${err.message}\n` +
            'The documentation build will continue without an updated Moss index.'
        )
        debug('Moss index sync error', err)
      }
    }
  }
}
