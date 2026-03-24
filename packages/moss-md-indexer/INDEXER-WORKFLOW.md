# 🔍 Search Indexer Workflow

## 1. The High-Level Process

> **Note**: `vp` is the VitePress module (`import * as vitepress from 'vitepress'`), providing access to VitePress's internal APIs.

- **Scan**: Finds all .md files in your documentation folder.

  ```typescript
  const siteConfig = await vp.resolveConfig(absRoot, 'build')
  // siteConfig.pages contains all markdown file paths
  ```

- **Render**: Converts Markdown to HTML (using VitePress's own engine).

  ```typescript
  const md = await vp.createMarkdownRenderer(
    siteConfig.srcDir,
    siteConfig.markdown,
    siteConfig.site.base,
    siteConfig.logger
  )
  const html = await md.renderAsync(processedContent, env)
  ```

- **Parse**: Breaks the HTML into tiny pieces (Headers, Paragraphs, Code Blocks).
- **Context**: Tags each piece with its parent Header (so you know where it came from).
- **Save**: Exports a single index.json.

## 2. Walkthrough Example

Let's trace a single file named `guide.md` through the machine.

### The Input (guide.md)

````markdown
# Installation

To install the package, run this command:

```bash
npm install my-app
```

## Prerequisites

Ensure you have Node.js installed.
````

### Step 1: Render to HTML

The builder converts the Markdown to HTML in memory.

```html
<h1 id="installation">Installation</h1>
<p>To install the package, run this command:</p>
<pre><code>npm install my-app</code></pre>
<h2 id="prerequisites">Prerequisites</h2>
<p>Ensure you have Node.js installed.</p>
```

### Step 2: Build Hierarchy

The script scans for headings (h1-h6) first to create a map.

- **Found**: `<h1 id="installation">`
  - Map: ID `installation` → Title: "Installation"
- **Found**: `<h2 id="prerequisites">`
  - Map: ID `prerequisites` → Title: "Prerequisites"

### Step 3: Chunking & Context

The script iterates through the content elements. It looks "up" the DOM to find which header owns the content.

#### Chunk 1: The Header (H1)

- **Element**: `<h1 id="installation">Installation</h1>`
- **Context**: Uses `getHeadingContext()` to look for previous sibling headings. Since this is the first heading, it falls back to `pageTitle`.
- **Action**: Creates a search record with `type: "header"`.

#### Chunk 2: The Paragraph

- **Element**: `<p>To install...</p>`
- **Context**: It looks up and sees `h1#installation`.
- **Action**: Creates a search record linking this text to "Installation".

#### Chunk 3: The Code Block

- **Element**: `<pre>npm install...</pre>`
- **Context**: It looks up and still sees `h1#installation`.
- **Action**: Creates a search record linking this code to "Installation".

#### Chunk 4: The Header (H2)

- **Element**: `<h2 id="prerequisites">Prerequisites</h2>`
- **Context**: Uses `getHeadingContext()` and finds the previous sibling `h1#installation` (walking backwards up the DOM).
- **Action**: Creates a search record with `type: "header"`. The context title is "Installation" (the parent H1).

#### Chunk 5: The Paragraph

- **Element**: `<p>Ensure you have Node.js...</p>`
- **Context**: It looks up and sees `h2#prerequisites` (the nearest previous heading).
- **Action**: Creates a search record linking this text to "Prerequisites".

## 3. The Output (index.json)

The script outputs a flat list. Note how `guide.md` became 6 separate records.

```json
[
  // 1. The Page Title
  {
    "id": "guide",
    "text": "Installation",
    "metadata": {
      "title": "Installation",
      "groupId": "guide",
      "type": "page",
      "groupTitle": "Installation",
      "displayBreadcrumb": "Installation",
      "sanitizedText": "Installation",
      "navigation": "guide"
    }
  },

  // 2. The Header (H1)
  {
    "id": "guide#installation-0",
    "text": "Installation\n\nInstallation",
    "metadata": {
      "title": "Installation",
      "groupId": "guide",
      "type": "header",
      "groupTitle": "Installation",
      "displayBreadcrumb": "Installation",
      "sanitizedText": "Installation",
      "navigation": "guide#installation"
    }
  },

  // 3. The Paragraph Text
  {
    "id": "guide#installation-1", 
    "text": "Installation\n\nTo install the package, run this command:",
    "metadata": {
      "title": "Installation",
      "groupId": "guide",
      "type": "text",
      "groupTitle": "Installation",
      "displayBreadcrumb": "Installation",
      "sanitizedText": "To install the package, run this command:",
      "navigation": "guide#installation"
    }
  },

  // 4. The Code Block
  {
    "id": "guide#installation-2",
    "text": "Installation\n\nnpm install my-app",
    "metadata": {
      "title": "Installation",
      "groupId": "guide",
      "type": "code",
      "groupTitle": "Installation",
      "displayBreadcrumb": "Installation",
      "sanitizedText": "npm install my-app",
      "navigation": "guide#installation"
    }
  },

  // 5. The Header (H2)
  {
    "id": "guide#installation-3",
    "text": "Installation\n\nPrerequisites",
    "metadata": {
      "title": "Installation",
      "groupId": "guide",
      "type": "header",
      "groupTitle": "Installation",
      "displayBreadcrumb": "Installation",
      "sanitizedText": "Prerequisites",
      "navigation": "guide#installation"
    }
  },

  // 6. The Paragraph under H2
  {
    "id": "guide#prerequisites-4",
    "text": "Prerequisites\n\nEnsure you have Node.js installed.",
    "metadata": {
      "title": "Prerequisites",
      "groupId": "guide",
      "type": "text",
      "groupTitle": "Installation",
      "displayBreadcrumb": "Installation > Prerequisites",
      "sanitizedText": "Ensure you have Node.js installed.",
      "navigation": "guide#prerequisites"
    }
  }
]
```

## 4. Field Calculation Details

Each field in the index is calculated as follows:

### Top-Level Fields

- **`id`**: Unique identifier for each chunk

  ```typescript
  const uniqueId = anchor
    ? `${fileId}#${anchor}-${blockIndex}`
    : `${fileId}-${blockIndex}`
  ```

  - `fileId`: Derived from the file path (e.g., `guide.md` → `guide`)
  - `anchor`: The heading ID found via `getHeadingContext()` (e.g., `installation`)
  - `blockIndex`: Incremental counter for chunks within the same section

- **`text`**: Searchable content with context injection

  ```typescript
  text: `${title}\n\n${content}`
  ```

  - `title`: The nearest heading text (found by walking up the DOM)
  - `content`: The actual chunk content (paragraph, code block, etc.)

### Metadata Fields

- **`metadata.title`**: The text of the nearest parent heading

  ```typescript
  // Found by walking up DOM tree using prevAll()
  const prev = current.prevAll('h1, h2, h3, h4, h5, h6').first()
  title = headingInfo.text
  ```

  - Falls back to `pageTitle` if no heading is found

- **`metadata.groupId`**: The page identifier (same for all chunks from one page)

  ```typescript
  const groupId = fileId  // e.g., "guide"
  ```

  - Derived from the file path relative to `srcDir`

- **`metadata.type`**: The content type

  ```typescript
  // Determined by the HTML element being processed:
  'page'   // Page-level entry (created first)
  'header' // Heading element (h1-h6)
  'text'   // Paragraph, list item, blockquote, or table cell
  'code'   // Code block (<pre>)
  ```

- **`metadata.groupTitle`**: The page title

  ```typescript
  const groupTitle = pageTitle  // From frontmatter.title or filename
  ```

- **`metadata.displayBreadcrumb`**: Hierarchical breadcrumb path

  ```typescript
  let displayBreadcrumb = hierarchy.join(' > ') || pageTitle
  // Removes pageTitle prefix if present
  if (displayBreadcrumb.startsWith(pageTitle + ' > ')) {
    displayBreadcrumb = displayBreadcrumb.slice(pageTitle.length + 3)
  }
  ```

  - `hierarchy`: Array built from heading levels (e.g., `["Installation", "Quick Start"]`)
  - Example: `"Installation > Quick Start"` or just `"Installation"`

- **`metadata.sanitizedText`**: Normalized content for display

  ```typescript
  const sanitizedText = content.replace(/\s+/g, ' ').trim()
  ```

  - Replaces all whitespace (newlines, tabs, multiple spaces) with single spaces

- **`metadata.navigation`**: The URL anchor to navigate to

  ```typescript
  const navigation = anchor
    ? `${fileId}#${anchor}`  // e.g., "guide#installation"
    : fileId                 // e.g., "guide"
  ```

  - Used by the search UI to jump directly to the relevant section

### Helper Functions

**`getHeadingContext()`**: Walks up the DOM tree to find the nearest heading

```typescript
while (current.length > 0) {
  const prev = current.prevAll('h1, h2, h3, h4, h5, h6').first()
  if (prev.length > 0) {
    anchor = prev.attr('id') || ''
    // Get heading info from headingMap
    break
  }
  current = current.parent()
}
```

**`fileId` calculation**: Converts file path to page identifier

```typescript
let fileId = slash(path.relative(siteConfig.srcDir, absolutePath))
// Handle index.md → "index"
if (fileId === 'index.md') {
  fileId = 'index'
} else {
  fileId = fileId.replace(/(^|\/)index\.md$/, '$1')
}
// Remove .md extension, add .html if cleanUrls is false
fileId = fileId.replace(/\.md$/, siteConfig.cleanUrls ? '' : '.html')
```

**Hierarchy building**: Tracks heading levels to build breadcrumbs

```typescript
// Extract all headings first
$('h1, h2, h3, h4, h5, h6').each((_index, el) => {
  const level = parseInt(tagName.slice(1))  // h1 → 1, h2 → 2, etc.
  hierarchy.length = level - 1  // Reset deeper levels
  hierarchy[level - 1] = text   // Set current level
  headingMap.set(id, { level, text, hierarchy: [...hierarchy] })
})
```

## 5. Why this matters?

- **Precision**: If a user searches "npm install", they go straight to the code block, not just the top of the page.
- **Context**: Even though the code block doesn't say "Installation", the index adds that title to the text field so it matches relevant searches.
