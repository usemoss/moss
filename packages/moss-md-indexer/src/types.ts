// types.ts

export interface MossMetadata {
  title: string
  groupId: string
  type: 'page' | 'header' | 'text' | 'code'
  groupTitle: string
  displayBreadcrumb: string
  sanitizedText: string
  navigation: string
  [key: string]: string
}

export interface MossDocument {
  id: string
  text: string
  metadata: MossMetadata
}

export interface MossCreds {
  projectId: string
  projectKey: string
  indexName: string
  modelName: string
}

export interface MarkdownRenderer {
  renderAsync?: (content: string, env: any) => Promise<string>
  render: (content: string, env: any) => string
  parse: (content: string, env: any) => any[]
  // Add other internal MD properties if needed
}

export interface VitePressSiteConfig {
  srcDir: string
  markdown: any // Markdown options
  site: {
    base: string
  }
  logger: any // using any to avoid dependency on vite types
  pages: string[]
  cleanUrls?: boolean
}

export interface VitePressModule {
  resolveConfig: (root: string, command: 'build' | 'serve') => Promise<VitePressSiteConfig>
  createMarkdownRenderer: (
    srcDir: string, 
    options: any, 
    base: string, 
    logger: any
  ) => Promise<MarkdownRenderer>
  processIncludes?: (
    md: MarkdownRenderer, 
    srcDir: string, 
    content: string, 
    file: string, 
    includes: string[], 
    cleanUrls: boolean
  ) => string
}

export interface VitePressLoader {
  resolveConfig: VitePressModule['resolveConfig']
  createMarkdownRenderer: VitePressModule['createMarkdownRenderer']
  processIncludes: Required<VitePressModule>['processIncludes']
  slash: (p: string) => string
}
