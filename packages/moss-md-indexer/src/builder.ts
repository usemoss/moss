import fs from 'fs-extra'
import path from 'node:path'
import matter from 'gray-matter'
import pLimit from 'p-limit'
import * as cheerio from 'cheerio'
import type { VitePressModule, MarkdownRenderer, MossDocument, MossMetadata } from './types.js'

// Converts backslashes to forward slashes for cross-platform consistency
function slash(p: string): string {
  return p.replace(/\\/g, '/')
}

interface HeadingInfo {
  level: number
  text: string
  hierarchy: string[]
}

interface HeadingContext {
  anchor: string
  hierarchy: string[]
  title: string
}

// ---------------------- PARSER LOGIC ----------------------
async function parseHtmlToSections(html: string, fileId: string, pageTitle: string, md: MarkdownRenderer, env: Record<string, any>) {
  const sections: MossDocument[] = []

  // creates a page document entry
  sections.push({
    id: fileId,
    text: pageTitle,
    metadata: {
      title: pageTitle,
      groupId: fileId,
      type: 'page',
      groupTitle: pageTitle,
      displayBreadcrumb: pageTitle,
      sanitizedText: pageTitle,
      navigation: fileId
    }
  })

  // Load HTML into cheerio for querying
  const $ = cheerio.load(html)
  
  // Build hierarchy map: heading ID -> { level, text, hierarchy }
  const headingMap = new Map<string, HeadingInfo>()
  const hierarchy: string[] = []
  
  // extract all headings and build hierarchy
  $('h1, h2, h3, h4, h5, h6').each((_index: number, el: cheerio.Element) => {
    const $heading = $(el)
    // Get tag name from element - cheerio elements have a 'name' property in some versions, or use prop
    const tagName = (el as any).name || $heading.prop('tagName') || ''
    if (!tagName) return
    
    const level = parseInt(tagName.slice(1))
    if (!level || isNaN(level)) return
    
    const text = $heading.text().trim()
    const id = $heading.attr('id') || ''
    
    // Update hierarchy array
    hierarchy.length = level - 1
    hierarchy[level - 1] = text
    
    if (id) {
      headingMap.set(id, {
        level,
        text,
        hierarchy: [...hierarchy]
      })
    }
  })
  
  // Helper to find current heading context for an element
  const getHeadingContext = (el: cheerio.Element): HeadingContext => {
    let current = $(el)
    let anchor = ''
    let contextHierarchy: string[] = []
    let title = pageTitle
    
    // Walk up the DOM to find the nearest heading
    while (current.length > 0) {
      const prev = current.prevAll('h1, h2, h3, h4, h5, h6').first()
      if (prev.length > 0) {
        anchor = prev.attr('id') || ''
        const headingInfo = headingMap.get(anchor)
        if (headingInfo) {
          contextHierarchy = headingInfo.hierarchy
          title = headingInfo.text
        }
        break
      }
      current = current.parent()
    }
    
    return { anchor, hierarchy: contextHierarchy, title }
  }
  
  // Helper to create a section chunk
  const createSection = (content: string, anchor: string, hierarchy: string[], title: string, blockIndex: number, type: MossMetadata['type']): MossDocument | null => {
    if (!content.trim()) return null
    
    const groupId = fileId
    const groupTitle = pageTitle
    
    // Breadcrumb logic
    let displayBreadcrumb = hierarchy.join(' > ') || pageTitle
    if (displayBreadcrumb.startsWith(pageTitle + ' > ')) {
      displayBreadcrumb = displayBreadcrumb.slice(pageTitle.length + 3)
    }
    // If hierarchy is empty, displayBreadcrumb will be pageTitle (no need to set to empty)
    
    const sanitizedText = content.replace(/\s+/g, ' ').trim()
    const uniqueId = anchor
      ? `${fileId}#${anchor}-${blockIndex}`
      : `${fileId}-${blockIndex}`
    
    // Navigation ID: keep it "pure" (no block index suffix)
    // - With anchors: use fileId#anchor so multiple chunks share the same target
    // - Without anchors: use the page-level fileId (top of page)
    const navigation = anchor
      ? `${fileId}#${anchor}`
      : fileId
    
    return {
      id: uniqueId,
      text: `${title}\n\n${content}`, // Inject heading context
      metadata: {
        title,
        groupId,
        type,
        groupTitle,
        displayBreadcrumb,
        sanitizedText,
        navigation
      }
    }
  }
  
  // Helper function to process elements
  function processElements(
    selector: string,
    type: MossMetadata['type'],
    skipIfHasParagraphs = false
  ) {
    $(selector).each((_index: number, el: cheerio.Element) => {
      if (skipIfHasParagraphs && $(el).find('p').length > 0) return

      const text = $(el).text().trim()
      if (!text) return

      const context = getHeadingContext(el)

      const section = createSection(text, context.anchor, context.hierarchy, context.title, blockCounter++, type)
      if (section) sections.push(section)
    })
  }
  
  // Extract granular chunks: paragraphs, list items, code blocks
  let blockCounter = 0
  
  // Process paragraphs
  processElements('p', 'text')
  
  // Process list items (only if they don't contain paragraphs, to avoid duplicates)
  processElements('li', 'text', true)
  
  // Process code blocks
  processElements('pre', 'code')

  // Process blockquotes (only if they don't contain paragraphs)
  processElements('blockquote', 'text', true)

  // Process headers
  processElements('h1, h2, h3, h4, h5, h6', 'header')

  // Process table cells (only if they don't contain paragraphs)
  processElements('td', 'text', true)
  
  return sections
}

// ----------------------- INDEX BUILDING LOGIC ---------------------- 

/*
  buildIndex:
  - load VitePress and resolve site config
  - create markdown renderer
  - iterate site pages (concurrent via pLimit)
  - read file, parse frontmatter, skip pages with search: false
  - process includes, parse tokens, convert to sections
  - write combined sections JSON to outputFile
*/

export interface BuildOptions {
  outputFile?: string
}

export async function buildJsonDocs(mdRoot: string, options: BuildOptions = {}) {
  const absRoot = path.resolve(mdRoot)
  console.log(`Loading VitePress config from: ${absRoot}`)

  // VitePress is a pure ESM module - import it directly
  const vp = await import('vitepress') as VitePressModule
  if (!vp?.resolveConfig || !vp?.createMarkdownRenderer) {
    throw new Error('Incompatible VitePress version: missing renderer APIs')
  }

  const siteConfig = await vp.resolveConfig(absRoot, 'build')
  if (!siteConfig) throw new Error(`Could not resolve VitePress config in ${absRoot}`)

  const md = await vp.createMarkdownRenderer(
    siteConfig.srcDir,
    siteConfig.markdown,
    siteConfig.site.base,
    siteConfig.logger
  )

  console.log(`Processing ${siteConfig.pages.length} pages...`)

  const limit = pLimit(10)

  const results = await Promise.all(
    siteConfig.pages.map((page: string) => limit(async () => {
      const absolutePath = path.join(siteConfig.srcDir, page)
      if (!fs.existsSync(absolutePath)) return []
      
      try {
        const rawContent = await fs.readFile(absolutePath, 'utf-8')
        const { data: frontmatter, content } = matter(rawContent)
        
        if (frontmatter.search === false) return []

        const processIncludes = vp.processIncludes || ((_md: any, _src: any, c: string) => c)
        const processedContent = processIncludes(md, siteConfig.srcDir, content, absolutePath, [], siteConfig.cleanUrls || false)
        
        const env: Record<string, any> = {
          path: absolutePath,
          relativePath: slash(path.relative(siteConfig.srcDir, absolutePath)),
          cleanUrls: siteConfig.cleanUrls || false
        }
        
        // Render markdown to HTML for granular parsing
        // VitePress markdown renderer may use 'render' (sync) or 'renderAsync' (async)
        const html = md.renderAsync 
          ? await md.renderAsync(processedContent, env)
          : md.render(processedContent, env)
        
        let fileId = slash(path.relative(siteConfig.srcDir, absolutePath))
        
        // FIX: Handle index.md specifically to ensure it doesn't become empty string
        if (fileId === 'index.md') {
          fileId = 'index'
        } else {
          // Your existing logic for other files
          fileId = fileId.replace(/(^|\/)index\.md$/, '$1')
        }
        
        // Ensure extensions are handled as you prefer (e.g. switching .md to .html)
        fileId = fileId.replace(/\.md$/, siteConfig.cleanUrls ? '' : '.html')
        
        // Final safety check
        if (!fileId) fileId = 'index'
        
        return await parseHtmlToSections(html, fileId, frontmatter.title || path.basename(page, '.md'), md, env)
      } catch (e: any) {
        console.warn(`⚠️ Skipping ${page}: ${e.message}`)
        return []
      }
    }))
  )

  const mossDocuments = results.flat()
  
  if (mossDocuments.length === 0) {
    throw new Error("Build failed: 0 documents indexed. Check VitePress loading logic.")
  }
  
  if (options.outputFile) {
    await fs.ensureDir(path.dirname(options.outputFile))
    await fs.outputJSON(options.outputFile, mossDocuments, { spaces: 2 })
    console.log(`✅ Index built: ${mossDocuments.length} chunks saved to ${options.outputFile}`)
  } else {
    console.log(`✅ Index built in memory: ${mossDocuments.length} chunks generated`)
  }

  return mossDocuments
}
