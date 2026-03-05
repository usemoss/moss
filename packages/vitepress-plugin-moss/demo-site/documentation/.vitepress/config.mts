import { defineConfig } from 'vitepress'
import { mossIndexerPlugin } from 'vitepress-plugin-moss'
import dotenv from 'dotenv'

dotenv.config({ path: '../.env' })

// https://vitepress.dev/reference/site-config
export default defineConfig({
  vite: {
    plugins: [mossIndexerPlugin()]
  },
  srcDir: "docs",

  title: "Moss SDK Documentation",
  description: "Get real-time retrieval inside apps, browsers, and enterprise agents — with centralized management, analytics, and scale built in.",
  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }]
  ],
  themeConfig: {
    search: {
      provider: 'moss' as any,
      options: {
        projectId: process.env.MOSS_PROJECT_ID || 'your-project-id',
        projectKey: process.env.MOSS_PROJECT_KEY || 'your-project-key',
        indexName: process.env.MOSS_INDEX_NAME || 'moss-sdk-docs',
      } as any,
    },
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Moss Portal', link: 'https://usemoss.dev', target: '_blank', rel: 'noopener noreferrer' },
      { text: 'Getting Started', link: '/getting-started' },
      { text: 'JavaScript SDK', link: '/reference/js/README.md' },
      { text: 'Python SDK', link: '/reference/python/README.md' }
    ],

    sidebar: [
      {
        text: 'Guides',
        items: [
          { text: 'Getting Started', link: '/getting-started' }
        ]
      },
      {
        text: 'SDK References',
        items: [
          { text: 'JavaScript SDK Overview', link: '/reference/js/README.md' },
          { text: 'JavaScript API Reference', link: '/reference/js/globals.md' },
          { text: 'Python SDK Overview', link: '/reference/python/README.md' },
          { text: 'Python API Reference', link: '/reference/python/globals.md' },
          { text: 'Samples', link: 'https://github.com/usemoss/moss-samples' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/usemoss/moss-samples' }
    ]
  }
})
